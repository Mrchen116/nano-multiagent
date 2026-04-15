"""Canonical session aggregate models shared across runtime layers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Session:
    """Represent a persisted agent session.

    First-class fields carry the structured runtime configuration that is
    always known at creation time.  ``metadata`` is reserved for arbitrary
    pass-through data that higher layers (e.g. IM, gateway) inject and read
    back without the session layer needing to understand it.
    """

    session_id: str
    status: str
    created_at: str
    workspace_root: Path
    system_prompt: str | None = None
    """Frozen system prompt for this session; None means use the runtime default."""
    skills: tuple[str, ...] | None = None
    """Skill names available in this session; None means use the runtime defaults."""
    tool_allowlist: tuple[str, ...] | None = None
    """Allowed tool names; None means use the product/runtime defaults."""
    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary pass-through data (e.g. conversation_type, participant_agent_ids)."""
