"""Canonical session store contract shared by platform persistence backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from nano_multiagent.session.entries import SessionEventEntry


@dataclass(frozen=True, slots=True)
class LoadedSession:
    """Bundle loaded session id, ordered events, and optional snapshot."""

    session_id: str
    events: tuple[SessionEventEntry, ...]
    snapshot: Mapping[str, Any] | None = None


class SessionStore(ABC):
    """Define persistence boundary for session events and snapshots."""

    # STORE BOUNDARY: manager owns session semantics; stores only persist and
    # retrieve opaque serialized events/snapshots in order.
    @abstractmethod
    def append_event(self, session_id: str, entry: SessionEventEntry) -> None:
        """Append one state-change event for a session."""

    @abstractmethod
    def load_session(self, session_id: str) -> LoadedSession | None:
        """Load session events and optional snapshot by session id."""

    @abstractmethod
    def save_snapshot(self, session_id: str, snapshot: Mapping[str, Any]) -> None:
        """Persist a snapshot for fast session rebuild."""
