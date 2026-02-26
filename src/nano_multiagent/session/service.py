import os
from pathlib import Path

from .manager import SessionManager
from .models import Session
from .stores.base import SessionStore
from .stores.sqlite_store import SQLiteSessionStore


class SessionService:
    def __init__(self, *, store: SessionStore | None = None, manager: SessionManager | None = None) -> None:
        active_store = store or SQLiteSessionStore(db_path=_default_sqlite_store_path())
        self._manager = manager or SessionManager(store=active_store)

    def create_session(self) -> Session:
        return self._manager.create_session()

    def get_session(self, session_id: str) -> Session | None:
        return self._manager.get_session(session_id)


def _default_sqlite_store_path() -> Path:
    configured_path = os.getenv("NANO_MULTIAGENT_SESSION_DB")
    if configured_path:
        return Path(configured_path)
    return Path(".nano_multiagent") / "sessions.sqlite3"
