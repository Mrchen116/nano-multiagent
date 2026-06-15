"""Chat history persistence hook for personal_assistant (see docs/specs/gateway/spec.md).

refactor-406-M2: migrated verbatim from the dissolved
``agent/products/personal_assistant/hooks/chat_history.py``. M1 R6 planned to move PA
hooks into ``src/personal_assistant/`` and wire them via ``build_kernel(hooks=…)`` but
shipped ``hooks=[]`` — chat history persistence (a M249 behavior) was silently lost.
This refactor is behavior-preserving, so the gap is closed here: the hook is supplied
to ``build_pa_kernel(hooks=[setup])``.

Implements the ``after_agent_reply`` semantics (as defined in docs/specs/gateway/spec.md)
using three existing hook events, because ``after_agent_reply`` is not a registered
event type in core.

Event chain per turn:
    1. ``input`` (intercept) → capture user text; store in ``_pending[session_id]``
    2. ``message_end`` (observe) → capture last assistant content per session
    3. ``agent_end`` (observe) → flush user+assistant pair to JSONL; clear pending

JSONL format (one object per line, append mode):
    {"ts": "<ISO8601Z>", "role": "user"|"assistant", "content": "<text>"}

Path convention (SPEC §12):
    <workspace_root>/chat_history/<session_id>.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# Module-level state: keyed by session_id, holds captured turn data.
# Dict access is GIL-protected for simple get/set; no explicit lock needed.
_pending: dict[str, dict[str, str]] = {}


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string with Z suffix."""

    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_line(path: Path, record: dict[str, str]) -> None:
    """Append one JSON record as a single line to path.

    Side Effects:
        Creates parent directories if they do not exist.
        Opens the file in append mode; never truncates existing content.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def setup(hooks: Any) -> None:  # noqa: ANN401
    """Register input/message_end/agent_end handlers that together persist chat history.

    Args:
        hooks: Hook registration API provided by the loader (HookAPI or HookRegistry).

    Side Effects:
        Registers three event handlers that write JSONL to the agent workspace.
        No core/ or platform/ files are modified.
    """

    def _on_input(payload: Mapping[str, Any], ctx: Any) -> None:
        """Capture user text from the input event; store for later flush."""
        text = payload.get("text")
        if not isinstance(text, str):
            return None
        _pending[ctx.session_id] = {"user_text": text}
        # Return None: no transform/interception; let input pass through unchanged.
        return None

    def _on_message_end(payload: Mapping[str, Any], ctx: Any) -> None:
        """Capture the last assistant message content for this session."""
        role = payload.get("role")
        if role != "assistant":
            return None
        content = payload.get("content")
        if not isinstance(content, str):
            return None
        session_state = _pending.get(ctx.session_id)
        if session_state is None:
            # Guard: message_end arrived without a preceding input event; skip.
            return None
        session_state["assistant_text"] = content
        return None

    def _on_agent_end(payload: Mapping[str, Any], ctx: Any) -> None:
        """Flush captured turn data to JSONL and clear per-session pending state."""
        session_state = _pending.pop(ctx.session_id, None)
        if session_state is None:
            return None

        workspace_root = ctx.metadata.get("cwd") if ctx.metadata else None
        if not isinstance(workspace_root, str) or not workspace_root:
            # No workspace configured; skip silently as per SPEC §12 (no side effect).
            return None

        user_text = session_state.get("user_text", "")
        assistant_text = session_state.get("assistant_text", "")

        jsonl_path = Path(workspace_root) / "chat_history" / f"{ctx.session_id}.jsonl"
        _append_line(
            jsonl_path, {"ts": _now_iso(), "role": "user", "content": user_text}
        )
        _append_line(
            jsonl_path,
            {"ts": _now_iso(), "role": "assistant", "content": assistant_text},
        )
        return None

    # Priority 50: run after communication_context (priority=200) but before defaults.
    # timeout_ms=1000: file I/O is local; generous budget to avoid blocking shutdown.
    hooks.on("input", _on_input, priority=50, timeout_ms=1000)
    hooks.on("message_end", _on_message_end, priority=50, timeout_ms=1000)
    hooks.on("agent_end", _on_agent_end, priority=50, timeout_ms=1000)
