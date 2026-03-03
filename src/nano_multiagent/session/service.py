"""Facade for session manager wiring and default store selection."""

import os
from pathlib import Path
from typing import Any, Mapping

from .manager import SessionManager
from .models import Session
from .stores.base import SessionStore
from .stores.sqlite_store import SQLiteSessionStore


class SessionService:
    """Expose session APIs while hiding store/manager construction details."""

    def __init__(self, *, store: SessionStore | None = None, manager: SessionManager | None = None) -> None:
        active_store = store or SQLiteSessionStore(db_path=_default_sqlite_store_path())
        self._manager = manager or SessionManager(store=active_store)

    @property
    def manager(self) -> SessionManager:
        """Return underlying manager for advanced flows needing raw access."""

        return self._manager

    def create_session(self, *, title: str | None = None, metadata: Mapping[str, Any] | None = None) -> Session:
        """Create a session via manager using optional title/metadata."""

        return self._manager.create_session(title=title, metadata=metadata)

    def get_session(self, session_id: str) -> Session | None:
        """Return session by id or `None` when no persisted state exists."""

        return self._manager.get_session(session_id)

    def list_sessions(self, *, limit: int, offset: int) -> tuple[tuple[Session, ...], bool]:
        """List sessions with pagination and `has_more` result."""

        return self._manager.list_sessions(limit=limit, offset=offset)


def _default_sqlite_store_path() -> Path:
    configured_path = os.getenv("NANO_MULTIAGENT_SESSION_DB")
    if configured_path:
        return Path(configured_path)
    return Path(".nano_multiagent") / "sessions.sqlite3"
