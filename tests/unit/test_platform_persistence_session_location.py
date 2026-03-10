"""Verify platform persistence exposes core session contracts plus platform stores."""

from nano_multiagent.core.session.store import LoadedSession as CoreLoadedSession
from nano_multiagent.core.session.store import SessionStore as CoreSessionStore
from nano_multiagent.platform.persistence.session import (
    JsonlSessionStore,
    LoadedSession,
    SQLiteSessionStore,
    SessionStore,
)
from nano_multiagent.platform.persistence.session.base import (
    LoadedSession as PlatformLoadedSession,
)
from nano_multiagent.platform.persistence.session.base import (
    SessionStore as PlatformSessionStore,
)
from nano_multiagent.platform.persistence.session.jsonl_store import (
    JsonlSessionStore as PlatformJsonlSessionStore,
)
from nano_multiagent.platform.persistence.session.sqlite_store import (
    SQLiteSessionStore as PlatformSQLiteSessionStore,
)
from nano_multiagent.platform.persistence.session import (
    JsonlSessionStore as LegacyJsonlSessionStore,
    LoadedSession as LegacyLoadedSession,
    SQLiteSessionStore as LegacySQLiteSessionStore,
    SessionStore as LegacySessionStore,
)
from nano_multiagent.core.session.store import (
    LoadedSession as LegacyLoadedSessionBase,
)
from nano_multiagent.core.session.store import SessionStore as LegacySessionStoreBase
from nano_multiagent.platform.persistence.session.jsonl_store import (
    JsonlSessionStore as LegacyJsonlSessionStoreModule,
)
from nano_multiagent.platform.persistence.session.sqlite_store import (
    SQLiteSessionStore as LegacySQLiteSessionStoreModule,
)


def test_platform_persistence_session_exports_core_contract_and_platform_backends() -> None:
    """Platform persistence must expose the core store contract plus platform backends."""
    assert SessionStore is CoreSessionStore
    assert LoadedSession is CoreLoadedSession
    assert SessionStore is PlatformSessionStore
    assert LoadedSession is PlatformLoadedSession
    assert JsonlSessionStore is PlatformJsonlSessionStore
    assert SQLiteSessionStore is PlatformSQLiteSessionStore

    assert SessionStore.__module__ == "nano_multiagent.core.session.store"
    assert LoadedSession.__module__ == "nano_multiagent.core.session.store"
    assert JsonlSessionStore.__module__ == "nano_multiagent.platform.persistence.session.jsonl_store"
    assert SQLiteSessionStore.__module__ == "nano_multiagent.platform.persistence.session.sqlite_store"


def test_old_session_stores_shim_still_works() -> None:
    """Legacy session store modules must stay as compat shims to core/platform exports."""
    assert LegacySessionStore is CoreSessionStore
    assert LegacyLoadedSession is CoreLoadedSession
    assert LegacyJsonlSessionStore is PlatformJsonlSessionStore
    assert LegacySQLiteSessionStore is PlatformSQLiteSessionStore

    assert LegacySessionStoreBase is CoreSessionStore
    assert LegacyLoadedSessionBase is CoreLoadedSession
    assert LegacyJsonlSessionStoreModule is PlatformJsonlSessionStore
    assert LegacySQLiteSessionStoreModule is PlatformSQLiteSessionStore
