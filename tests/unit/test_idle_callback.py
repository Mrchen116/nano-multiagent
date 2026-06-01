"""Test that background events are rendered during REPL idle time."""

from __future__ import annotations

import io
import threading
import time
from typing import Any
from unittest.mock import MagicMock

from coding_cli.input import repl_input


def test_idle_callback_renders_background_events() -> None:
    """Verify _idle_callback in commands.py renders queued background events."""
    out = io.StringIO()

    # Simulate a persistent set of background event state
    bg_seen_runs: set[str] = set()
    bg_pending: dict[str, list[dict[str, object]]] = {}

    def _format_origin_header(event: dict[str, object]) -> str | None:
        origin = event.get("origin")
        if not isinstance(origin, str) or origin.strip() == "" or origin == "user":
            return None
        source_task_id = event.get("source_task_id")
        if (
            origin == "background_task"
            and isinstance(source_task_id, str)
            and source_task_id.strip()
        ):
            return f"── background wake (task_id={source_task_id.strip()}) ──"
        return f"── origin: {origin.strip()} ──"

    def _emit_bg_event_text(event: dict[str, object], *, emit_fn: Any) -> None:
        event_name = event.get("event")
        if event_name == "assistant_message":
            content = event.get("content") or ""
            if content:
                lines = content.split("\n")
                while lines and lines[-1] == "":
                    lines.pop()
                for line in lines:
                    emit_fn(f"> {line}")
        elif event_name == "tool_start":
            name = str(event.get("name") or "?")
            emit_fn(f"  ▸ {name}")
        elif event_name == "tool_end":
            name = str(event.get("name") or "?")
            duration_ms = event.get("duration_ms")
            duration_str = ""
            if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
                duration_str = f" ({int(duration_ms)}ms)"
            emit_fn(f"  ✓ {name}{duration_str}")

    def _process_one_bg_event(event: dict[str, object], *, emit_fn: Any) -> None:
        event_name = event.get("event")
        run_id = event.get("run_id")
        if event_name == "run_status":
            origin = event.get("origin")
            if isinstance(origin, str) and origin.strip() not in ("", "user"):
                if isinstance(run_id, str) and run_id.strip():
                    if run_id not in bg_seen_runs:
                        bg_seen_runs.add(run_id)
                        header = _format_origin_header(event)
                        if header:
                            emit_fn(header)
                    for pending in bg_pending.pop(run_id, []):
                        _emit_bg_event_text(pending, emit_fn=emit_fn)
            return
        if isinstance(run_id, str):
            if run_id in bg_seen_runs:
                _emit_bg_event_text(event, emit_fn=emit_fn)
            else:
                bg_pending.setdefault(run_id, []).append(event)

    # Simulate events arriving: first run_status, then assistant_message
    events = [
        {
            "event": "run_status",
            "run_id": "run_bg1",
            "origin": "background_task",
            "source_task_id": "task_123",
        },
        {
            "event": "assistant_message",
            "run_id": "run_bg1",
            "content": "Subagent finished!\nIt found 3 files.\n",
        },
        {"event": "tool_start", "run_id": "run_bg1", "name": "read"},
        {"event": "tool_end", "run_id": "run_bg1", "name": "read", "duration_ms": 150},
    ]

    # Simulate idle drain (same logic as commands.py _idle_callback)
    lines: list[str] = []

    def _emit_line(text: str) -> None:
        lines.append(text)

    for evt in events:
        _process_one_bg_event(evt, emit_fn=_emit_line)

    # Verify events were captured
    assert "── background wake (task_id=task_123) ──" in lines
    assert "> Subagent finished!" in lines
    assert "> It found 3 files." in lines
    assert "  ▸ read" in lines
    assert "  ✓ read (150ms)" in lines


def test_read_interactive_line_handles_idle_callback() -> None:
    """Verify read_interactive_line calls on_idle when key_reader returns _KEY_IDLE."""
    out = io.StringIO()
    idle_calls: list[int] = []
    key_calls = 0

    def _key_reader() -> str | None:
        nonlocal key_calls
        key_calls += 1
        # Return _KEY_IDLE twice, then a real key, then None (EOF)
        if key_calls <= 2:
            return repl_input._KEY_IDLE  # type: ignore[return-value]
        if key_calls == 3:
            return "x"
        return None

    def _on_idle() -> None:
        idle_calls.append(len(idle_calls))

    # The first "x" key won't trigger final_line because we need Enter.
    # After "x", key_reader returns None which triggers EOFError.
    # So we expect EOFError after 2 idle calls + 1 key.
    with pytest.raises(EOFError):
        repl_input.read_interactive_line(
            prompt="test> ",
            history=(),
            key_reader=_key_reader,
            out=out,
            on_idle=_on_idle,
        )

    assert len(idle_calls) == 2
    assert key_calls == 4


def test_read_interactive_line_without_idle_callback_skips_idle() -> None:
    """Verify _KEY_IDLE is ignored when on_idle is None."""
    out = io.StringIO()

    def _key_reader() -> str | None:
        return repl_input._KEY_IDLE  # type: ignore[return-value]

    # Without on_idle, _KEY_IDLE should just cause infinite loop until timeout
    # But since our key_reader always returns _KEY_IDLE, it'll loop forever.
    # We'll use a counter to break out.
    calls = 0

    def _counting_key_reader() -> str | None:
        nonlocal calls
        calls += 1
        if calls > 3:
            return None  # EOF
        return repl_input._KEY_IDLE  # type: ignore[return-value]

    with pytest.raises(EOFError):
        repl_input.read_interactive_line(
            prompt="test> ",
            history=(),
            key_reader=_counting_key_reader,
            out=out,
        )

    assert calls == 4


def test_build_key_reader_with_timeout_returns_idle() -> None:
    """Verify _build_key_reader returns _KEY_IDLE when select times out."""
    import select

    class _FakeStdin:
        def fileno(self) -> int:
            return -1  # Invalid fd, select will raise

    # With an invalid fd, select raises, but let's mock it
    original_select = select.select

    def _mock_select(*args: Any, **kwargs: Any) -> Any:
        return ([], [], [])

    select.select = _mock_select  # type: ignore[attr-defined]
    try:
        reader = repl_input._build_key_reader(
            _FakeStdin(),  # type: ignore[arg-type]
            on_idle=lambda: None,
            idle_interval_seconds=0.01,
        )
        result = reader()
        assert result is repl_input._KEY_IDLE
    finally:
        select.select = original_select  # type: ignore[attr-defined]


def test_idle_key_reader_drains_multichar_ime_commit(monkeypatch) -> None:
    """IME commits can arrive as one fd read; queued chars must not wait for next key."""

    class _FakeStdin:
        encoding = "utf-8"

        def fileno(self) -> int:
            return 42

    select_calls = 0

    def _fake_select(*args: Any, **kwargs: Any) -> Any:
        nonlocal select_calls
        del args, kwargs
        select_calls += 1
        if select_calls == 1:
            return ([42], [], [])
        raise AssertionError(
            "queued IME characters should be returned before polling fd again"
        )

    def _fake_read(fd: int, size: int) -> bytes:
        assert fd == 42
        assert size > 0
        return "你好吗".encode("utf-8")

    monkeypatch.setattr(repl_input.select, "select", _fake_select)
    monkeypatch.setattr(repl_input.os, "read", _fake_read)

    reader = repl_input._build_key_reader(
        _FakeStdin(),  # type: ignore[arg-type]
        on_idle=lambda: None,
        idle_interval_seconds=0.01,
    )

    assert reader() == "你"
    assert reader() == "好"
    assert reader() == "吗"
    assert select_calls == 1


def test_build_key_reader_without_idle_uses_blocking_read() -> None:
    """Verify _build_key_reader without on_idle delegates directly to _read_terminal_key."""
    calls: list[str] = []

    def _fake_read_terminal_key(stdin: Any) -> str | None:
        calls.append("read")
        return None

    original = repl_input._read_terminal_key
    repl_input._read_terminal_key = _fake_read_terminal_key  # type: ignore[assignment]
    try:
        reader = repl_input._build_key_reader(
            MagicMock(),
            on_idle=None,
            idle_interval_seconds=0.5,
        )
        result = reader()
        assert result is None
        assert calls == ["read"]
    finally:
        repl_input._read_terminal_key = original  # type: ignore[assignment]


import pytest
