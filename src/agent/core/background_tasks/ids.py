"""Background task ID generation aligned with Claude Code conventions."""

from __future__ import annotations

import secrets


_AGENT_ID_PREFIX = "a"
_BASH_TASK_ID_PREFIX = "b"
_ID_HEX_LENGTH = 16


def generate_agent_id() -> str:
    """Return a new agent identifier: 'a' + 16 hex chars."""
    return f"{_AGENT_ID_PREFIX}{secrets.token_hex(_ID_HEX_LENGTH // 2)}"


def generate_bash_task_id() -> str:
    """Return a new bash task identifier: 'b' + 16 hex chars."""
    return f"{_BASH_TASK_ID_PREFIX}{secrets.token_hex(_ID_HEX_LENGTH // 2)}"
