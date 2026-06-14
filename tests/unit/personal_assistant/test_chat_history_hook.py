"""Unit tests for M249 chat_history hook.

Tests verify that the after_agent_reply-equivalent hook (implemented via
input/message_end/agent_end) appends JSONL entries to
<workspace_root>/chat_history/<session_id>.jsonl after each turn.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookAPI, HookRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(*, session_id: str = "sess-test", cwd: str | None = None) -> HookContext:
    """Build a HookContext with optional cwd metadata injected by runtime."""
    metadata: dict[str, Any] = {}
    if cwd is not None:
        metadata["cwd"] = cwd
    return HookContext(session_id=session_id, metadata=metadata)


def _setup_registry() -> tuple[HookRegistry, Any]:
    """Load the chat_history hook into a fresh registry; return registry + module."""
    # refactor-406-M2: chat_history hook migrated to src/personal_assistant/hooks/.
    from personal_assistant.hooks import chat_history

    registry = HookRegistry()
    api = HookAPI(
        registry, source="product", module_name="chat_history", file_path=None
    )
    chat_history.setup(api)
    return registry, chat_history


def _call_handler(
    registry: HookRegistry, event: str, payload: dict, ctx: HookContext
) -> Any:
    """Invoke the first registered handler for an event synchronously."""
    handlers = registry.handlers_for(event)
    assert handlers, f"no handler registered for {event}"
    return handlers[0].handler(payload, ctx)


def _simulate_turn(
    registry: HookRegistry,
    *,
    session_id: str,
    cwd: str,
    user_text: str,
    assistant_text: str,
) -> None:
    """Drive one full turn: input -> message_end -> agent_end."""
    ctx = _make_ctx(session_id=session_id, cwd=cwd)
    _call_handler(registry, "input", {"text": user_text}, ctx)
    _call_handler(
        registry,
        "message_end",
        {
            "content": assistant_text,
            "role": "assistant",
            "session_id": session_id,
            "turn_id": "turn-1",
            "message_id": "msg-1",
        },
        ctx,
    )
    _call_handler(
        registry,
        "agent_end",
        {
            "session_id": session_id,
            "turn_id": "turn-1",
            "completed": True,
            "stop_reason": "completed",
        },
        ctx,
    )


# ---------------------------------------------------------------------------
# R1 tests
# ---------------------------------------------------------------------------


def test_writes_user_and_assistant_lines_after_agent_end(tmp_path: Path) -> None:
    """After one turn, session JSONL contains exactly two lines: user then assistant."""
    registry, mod = _setup_registry()
    mod._pending.clear()

    session_id = "sess-001"
    _simulate_turn(
        registry,
        session_id=session_id,
        cwd=str(tmp_path),
        user_text="hello",
        assistant_text="hi there",
    )

    jsonl_path = tmp_path / "chat_history" / f"{session_id}.jsonl"
    assert jsonl_path.exists(), "JSONL file not created"
    lines = [
        json.loads(line) for line in jsonl_path.read_text().splitlines() if line.strip()
    ]
    assert len(lines) == 2
    assert lines[0]["role"] == "user"
    assert lines[0]["content"] == "hello"
    assert lines[1]["role"] == "assistant"
    assert lines[1]["content"] == "hi there"


def test_creates_directory_if_missing(tmp_path: Path) -> None:
    """chat_history/ subdirectory is created automatically when absent."""
    registry, mod = _setup_registry()
    mod._pending.clear()

    session_id = "sess-dir-create"
    workspace = tmp_path / "agent_workspace"
    # workspace itself exists but chat_history/ does not
    workspace.mkdir()

    _simulate_turn(
        registry,
        session_id=session_id,
        cwd=str(workspace),
        user_text="create dir?",
        assistant_text="yes",
    )

    chat_dir = workspace / "chat_history"
    assert chat_dir.is_dir(), "chat_history directory was not created"
    assert (chat_dir / f"{session_id}.jsonl").exists()


def test_appends_across_multiple_turns(tmp_path: Path) -> None:
    """Multiple turns accumulate lines without truncating the file."""
    registry, mod = _setup_registry()
    mod._pending.clear()

    session_id = "sess-multi"
    for i in range(3):
        _simulate_turn(
            registry,
            session_id=session_id,
            cwd=str(tmp_path),
            user_text=f"turn {i} user",
            assistant_text=f"turn {i} assistant",
        )

    jsonl_path = tmp_path / "chat_history" / f"{session_id}.jsonl"
    lines = [
        json.loads(line) for line in jsonl_path.read_text().splitlines() if line.strip()
    ]
    # 3 turns × 2 lines = 6 lines
    assert len(lines) == 6
    roles = [line["role"] for line in lines]
    assert roles == ["user", "assistant"] * 3


def test_skips_gracefully_when_no_cwd(tmp_path: Path) -> None:
    """When ctx.metadata lacks 'cwd', hook silently skips without raising."""
    registry, mod = _setup_registry()
    mod._pending.clear()

    session_id = "sess-no-cwd"
    ctx = _make_ctx(session_id=session_id, cwd=None)

    # Should not raise
    _call_handler(registry, "input", {"text": "hello"}, ctx)
    _call_handler(
        registry,
        "message_end",
        {
            "content": "hi",
            "role": "assistant",
            "session_id": session_id,
            "turn_id": "t1",
            "message_id": "m1",
        },
        ctx,
    )
    _call_handler(
        registry,
        "agent_end",
        {
            "session_id": session_id,
            "turn_id": "t1",
            "completed": True,
            "stop_reason": "completed",
        },
        ctx,
    )

    # No file should be created anywhere under tmp_path
    assert not list(tmp_path.glob("**/*.jsonl"))


def test_jsonl_line_fields_valid(tmp_path: Path) -> None:
    """Each JSONL line has 'ts', 'role', 'content' fields with correct types."""
    registry, mod = _setup_registry()
    mod._pending.clear()

    session_id = "sess-fields"
    _simulate_turn(
        registry,
        session_id=session_id,
        cwd=str(tmp_path),
        user_text="field check",
        assistant_text="all good",
    )

    jsonl_path = tmp_path / "chat_history" / f"{session_id}.jsonl"
    lines = [
        json.loads(line) for line in jsonl_path.read_text().splitlines() if line.strip()
    ]
    for line in lines:
        assert "ts" in line, "missing 'ts'"
        assert "role" in line, "missing 'role'"
        assert "content" in line, "missing 'content'"
        assert isinstance(line["ts"], str) and line["ts"], (
            "'ts' must be a non-empty string"
        )
        assert line["role"] in ("user", "assistant"), f"unexpected role: {line['role']}"
        assert isinstance(line["content"], str), "'content' must be a string"
