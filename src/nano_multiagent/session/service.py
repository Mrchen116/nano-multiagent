"""Facade for session manager wiring and default store selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .manager import SessionManager
from .models import Session
from .stores.base import SessionStore
from .stores.sqlite_store import SQLiteSessionStore

if TYPE_CHECKING:
    from nano_multiagent.platform.product import ProductProfile


class SessionService:
    """Expose session APIs while hiding store/manager construction details.

    Args:
        store: Explicit session store; takes priority over both ``profile`` and
            the default path when provided.
        manager: Explicit session manager; bypasses all store construction when
            provided.
        profile: Optional product profile; when given and ``store`` is not
            explicitly provided, the session database is placed at
            ``ConfigResolver(profile).session_db_path()`` (inside the product's
            global config directory).  When absent, falls back to legacy
            ``_default_sqlite_store_path()`` behavior.
    """

    def __init__(
        self,
        *,
        store: SessionStore | None = None,
        manager: SessionManager | None = None,
        profile: ProductProfile | None = None,
    ) -> None:
        if store is not None:
            active_store = store
        elif profile is not None:
            active_store = _store_from_profile(profile)
        else:
            active_store = SQLiteSessionStore(db_path=_default_sqlite_store_path())
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


def _store_from_profile(profile: ProductProfile) -> SQLiteSessionStore:
    """Construct a SQLiteSessionStore at the profile's resolved session db path.

    Args:
        profile: Product profile with ``global_config_home`` set.

    Returns:
        SQLiteSessionStore whose database file lives in the product's global
        config directory (never in the workspace).

    Raises:
        ValueError: When ``profile.global_config_home`` is not set.
    """

    from nano_multiagent.platform.config.resolver import ConfigResolver

    resolver = ConfigResolver(profile=profile)
    db_path = resolver.session_db_path()
    return SQLiteSessionStore(db_path=db_path)


def _default_sqlite_store_path() -> Path:
    """Return the legacy default SQLite path, respecting env override.

    Returns:
        Path from ``NANO_MULTIAGENT_SESSION_DB`` env var when set; otherwise
        ``.nano_multiagent/sessions.sqlite3`` relative to CWD.
    """

    configured_path = os.getenv("NANO_MULTIAGENT_SESSION_DB")
    if configured_path:
        return Path(configured_path)
    return Path(".nano_multiagent") / "sessions.sqlite3"
