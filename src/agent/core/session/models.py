"""Canonical session aggregate models shared across runtime layers."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Session:
    """Represent persisted high-level session metadata."""

    session_id: str
    status: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
