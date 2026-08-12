"""Unit tests for M249 chat_history hook.

Tests verify that the after_agent_reply-equivalent hook (implemented via
input/message_end/agent_end) appends JSONL entries to
<workspace_root>/.nanoassistant/chat_history/<session_id>.jsonl after each turn.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookAPI, HookRegistry
from personal_assistant.gateway.readable_input_projection import (
    ReadableInputProjectionStore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    *,
    session_id: str = "sess-test",
    cwd: str | None = None,
    workspace_config_root: str | None = None,
) -> HookContext:
    """Build a HookContext with optional cwd metadata injected by runtime."""
    metadata: dict[str, Any] = {}
    if cwd is not None:
        metadata["cwd"] = cwd
    if workspace_config_root is not None:
        metadata["workspace_config_root"] = workspace_config_root
    return HookContext(session_id=session_id, metadata=metadata)


def _setup_registry(
    readable_store: ReadableInputProjectionStore | None = None,
) -> tuple[HookRegistry, Any]:
    """Load the chat_history hook into a fresh registry; return registry + module."""
    # refactor-406-M2: chat_history hook migrated to src/personal_assistant/hooks/.
    from personal_assistant.hooks import chat_history

    registry = HookRegistry()
    api = HookAPI(
        registry, source="product", module_name="chat_history", file_path=None
    )
    chat_history.setup(api, readable_input_projection_store=readable_store)
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

    jsonl_path = tmp_path / ".nanoassistant" / "chat_history" / f"{session_id}.jsonl"
    assert jsonl_path.exists(), "JSONL file not created"
    assert not (tmp_path / "chat_history").exists()
    lines = [
        json.loads(line) for line in jsonl_path.read_text().splitlines() if line.strip()
    ]
    assert len(lines) == 2
    assert lines[0]["role"] == "user"
    assert lines[0]["content"] == "hello"
    assert lines[1]["role"] == "assistant"
    assert lines[1]["content"] == "hi there"


def test_writes_exact_readable_projection_without_stripping_user_shaped_header(
    tmp_path: Path,
) -> None:
    store = ReadableInputProjectionStore()
    model = (
        "[Web IM Mon 2026-08-10 09:17 CST] [Feishu Mon 2026-08-10 09:16 CST] user text"
    )
    readable = "[Feishu Mon 2026-08-10 09:16 CST] user text"
    store.stage_or_replace("sess-readable", model, readable)
    registry, mod = _setup_registry(store)
    mod._pending.clear()

    _simulate_turn(
        registry,
        session_id="sess-readable",
        cwd=str(tmp_path),
        user_text=model,
        assistant_text="ok",
    )

    path = tmp_path / ".nanoassistant" / "chat_history" / "sess-readable.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["content"] == readable


def test_no_exact_projection_keeps_input_payload_unchanged(tmp_path: Path) -> None:
    store = ReadableInputProjectionStore()
    store.stage_or_replace("sess-no-match", "different model", "different raw")
    registry, mod = _setup_registry(store)
    mod._pending.clear()
    raw = "[Feishu Mon 2026-08-10 09:16 CST] user-authored"

    _simulate_turn(
        registry,
        session_id="sess-no-match",
        cwd=str(tmp_path),
        user_text=raw,
        assistant_text="ok",
    )

    path = tmp_path / ".nanoassistant" / "chat_history" / "sess-no-match.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["content"] == raw


def test_creates_directory_if_missing(tmp_path: Path) -> None:
    """The PA config-root chat_history directory is created automatically."""
    registry, mod = _setup_registry()
    mod._pending.clear()

    session_id = "sess-dir-create"
    workspace = tmp_path / "agent_workspace"
    # workspace itself exists but the PA config-root history directory does not
    workspace.mkdir()

    _simulate_turn(
        registry,
        session_id=session_id,
        cwd=str(workspace),
        user_text="create dir?",
        assistant_text="yes",
    )

    chat_dir = workspace / ".nanoassistant" / "chat_history"
    assert chat_dir.is_dir(), "chat_history directory was not created"
    assert (chat_dir / f"{session_id}.jsonl").exists()


def test_uses_workspace_execution_scope_config_root(tmp_path: Path) -> None:
    """The kernel-provided config root is the authoritative history location."""
    registry, mod = _setup_registry()
    mod._pending.clear()
    config_root = tmp_path / ".custom-pa"
    ctx = _make_ctx(
        session_id="sess-scoped",
        cwd=str(tmp_path),
        workspace_config_root=str(config_root),
    )

    _call_handler(registry, "input", {"text": "hello"}, ctx)
    _call_handler(
        registry,
        "message_end",
        {"content": "hi", "role": "assistant"},
        ctx,
    )
    _call_handler(registry, "agent_end", {}, ctx)

    assert (config_root / "chat_history" / "sess-scoped.jsonl").is_file()
    assert not (tmp_path / ".nanoassistant" / "chat_history").exists()


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

    jsonl_path = tmp_path / ".nanoassistant" / "chat_history" / f"{session_id}.jsonl"
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

    jsonl_path = tmp_path / ".nanoassistant" / "chat_history" / f"{session_id}.jsonl"
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
