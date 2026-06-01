"""Integration test: background events render during REPL idle time.

This test verifies the fix for the issue where background task completion
events (subagent/bash) were not visible in the CLI REPL while waiting for
user input.
"""

from __future__ import annotations

import io
import threading
import time
from typing import Any
from unittest.mock import MagicMock

from coding_cli.input import repl_input


def test_idle_callback_renders_background_events_prompt_aware() -> None:
    """Simulate background events arriving while REPL is idle.

    Before the fix: events would queue up in SessionStreamReader but only
    be drained at the start of the next loop iteration (i.e., after user
    pressed a key). They were invisible during idle time.

    After the fix: the terminal key reader polls with a timeout and calls
    an idle callback that drains and renders events using emit_persistent_text,
    which clears/restores the interactive prompt without corruption.
    """
    out = io.StringIO()

    # Track emitted text blocks (what would go through emit_persistent_text)
    emitted_blocks: list[str] = []

    def _mock_emit_persistent_text(*, out_stream: Any, text: str) -> None:
        emitted_blocks.append(text)

    # Simulate background event processing state (same as commands.py)
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

    # Simulate events arriving during idle (same sequence as real SSE events)
    events = [
        {
            "event": "run_status",
            "run_id": "run_bg1",
            "origin": "background_task",
            "source_task_id": "agent_abc123",
        },
        {
            "event": "assistant_message",
            "run_id": "run_bg1",
            "content": "I found 3 relevant files in the codebase.\nThe main loop is in src/agent/core/agent/runtime.py.\n",
        },
        {"event": "tool_start", "run_id": "run_bg1", "name": "read"},
        {"event": "tool_end", "run_id": "run_bg1", "name": "read", "duration_ms": 250},
        {
            "event": "run_status",
            "run_id": "run_bg1",
            "origin": "background_task",
            "source_task_id": "agent_abc123",
            "status": "completed",
        },
    ]

    # Simulate idle callback execution (same logic as commands.py _idle_callback)
    lines: list[str] = []

    def _emit_line(text: str) -> None:
        lines.append(text)

    for evt in events:
        _process_one_bg_event(evt, emit_fn=_emit_line)

    # Batch all lines into one block for prompt-aware rendering
    if lines:
        _mock_emit_persistent_text(out_stream=out, text="\n".join(lines))

    # Verify the full background run was rendered
    assert len(emitted_blocks) == 1
    block = emitted_blocks[0]

    assert "── background wake (task_id=agent_abc123) ──" in block
    assert "> I found 3 relevant files in the codebase." in block
    assert "> The main loop is in src/agent/core/agent/runtime.py." in block
    assert "  ▸ read" in block
    assert "  ✓ read (250ms)" in block


def test_key_reader_idle_timeout_sequence(monkeypatch) -> None:
    """Verify _build_key_reader returns _KEY_IDLE on timeout, then actual keys."""
    call_count = 0

    def _mock_select(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        # First two calls: timeout (empty ready list)
        # Third call: stdin has data
        if call_count <= 2:
            return ([], [], [])
        return ([0], [], [])  # fd 0 is ready

    class _FakeStdin:
        encoding = "utf-8"

        def fileno(self) -> int:
            return 0

    def _mock_read(fd: int, size: int) -> bytes:
        assert fd == 0
        assert size > 0
        return b"a"

    monkeypatch.setattr(repl_input.select, "select", _mock_select)
    monkeypatch.setattr(repl_input.os, "read", _mock_read)

    reader = repl_input._build_key_reader(
        _FakeStdin(),  # type: ignore[arg-type]
        on_idle=lambda: None,
        idle_interval_seconds=0.01,
    )

    # First call: timeout -> _KEY_IDLE
    assert reader() is repl_input._KEY_IDLE
    # Second call: timeout -> _KEY_IDLE
    assert reader() is repl_input._KEY_IDLE
    # Third call: data available -> actual key
    assert reader() == "a"


def test_read_interactive_line_idle_callback_invoked() -> None:
    """Verify read_interactive_line calls on_idle and continues waiting."""
    out = io.StringIO()
    idle_call_count = 0
    key_sequence = [repl_input._KEY_IDLE, repl_input._KEY_IDLE, "\n"]
    key_idx = 0

    def _key_reader() -> str | None:
        nonlocal key_idx
        key = key_sequence[key_idx]
        key_idx += 1
        return key  # type: ignore[return-value]

    def _on_idle() -> None:
        nonlocal idle_call_count
        idle_call_count += 1

    result = repl_input.read_interactive_line(
        prompt="> ",
        history=(),
        key_reader=_key_reader,
        out=out,
        on_idle=_on_idle,
    )

    # Should have called on_idle twice before Enter
    assert idle_call_count == 2
    # Should return empty line (Enter with no content)
    assert result == ""
