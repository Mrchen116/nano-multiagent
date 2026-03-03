"""Session domain models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    """Represent persisted high-level session metadata."""

    session_id: str
    status: str
    created_at: str
