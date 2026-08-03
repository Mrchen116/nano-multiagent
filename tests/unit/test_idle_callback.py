"""Tests for REPL idle-aware input."""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import MagicMock

import pytest

from coding_cli.input import repl_input


def test_read_interactive_line_handles_idle_callback() -> None:
    out = io.StringIO()
    idle_calls: list[int] = []
    key_calls = 0

    def _key_reader() -> str | None:
        nonlocal key_calls
        key_calls += 1
        if key_calls <= 2:
            return repl_input._KEY_IDLE  # type: ignore[return-value]
        if key_calls == 3:
            return "x"
        return None

    with pytest.raises(EOFError):
        repl_input.read_interactive_line(
            prompt="test> ",
            history=(),
            key_reader=_key_reader,
            out=out,
            on_idle=lambda: idle_calls.append(len(idle_calls)),
        )

    assert len(idle_calls) == 2
    assert key_calls == 4


def test_read_interactive_line_without_idle_callback_skips_idle() -> None:
    out = io.StringIO()
    calls = 0

    def _key_reader() -> str | None:
        nonlocal calls
        calls += 1
        if calls > 3:
            return None
        return repl_input._KEY_IDLE  # type: ignore[return-value]

    with pytest.raises(EOFError):
        repl_input.read_interactive_line(
            prompt="test> ", history=(), key_reader=_key_reader, out=out
        )

    assert calls == 4


def test_build_key_reader_with_timeout_returns_idle(monkeypatch) -> None:
    class _FakeStdin:
        def fileno(self) -> int:
            return -1

    monkeypatch.setattr(repl_input.select, "select", lambda *_args: ([], [], []))

    reader = repl_input._build_key_reader(
        _FakeStdin(),  # type: ignore[arg-type]
        on_idle=lambda: None,
        idle_interval_seconds=0.01,
    )

    assert reader() is repl_input._KEY_IDLE


def test_idle_key_reader_drains_multichar_ime_commit(monkeypatch) -> None:
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
        return "你好吗".encode()

    monkeypatch.setattr(repl_input.select, "select", _fake_select)
    monkeypatch.setattr(repl_input.os, "read", _fake_read)
    reader = repl_input._build_key_reader(
        _FakeStdin(),  # type: ignore[arg-type]
        on_idle=lambda: None,
        idle_interval_seconds=0.01,
    )

    assert [reader(), reader(), reader()] == ["你", "好", "吗"]
    assert select_calls == 1


def test_build_key_reader_without_idle_uses_blocking_read(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_read_terminal_key(_stdin: Any) -> None:
        calls.append("read")

    monkeypatch.setattr(repl_input, "_read_terminal_key", _fake_read_terminal_key)

    reader = repl_input._build_key_reader(
        MagicMock(), on_idle=None, idle_interval_seconds=0.5
    )

    assert reader() is None
    assert calls == ["read"]
