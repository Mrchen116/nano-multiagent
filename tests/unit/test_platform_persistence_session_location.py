"""Verify platform/persistence/session is the canonical home for session stores."""

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
from nano_multiagent.session.stores import (
    JsonlSessionStore as LegacyJsonlSessionStore,
    LoadedSession as LegacyLoadedSession,
    SQLiteSessionStore as LegacySQLiteSessionStore,
    SessionStore as LegacySessionStore,
)
from nano_multiagent.session.stores.base import (
    LoadedSession as LegacyLoadedSessionBase,
)
from nano_multiagent.session.stores.base import SessionStore as LegacySessionStoreBase
from nano_multiagent.session.stores.jsonl_store import (
    JsonlSessionStore as LegacyJsonlSessionStoreModule,
)
from nano_multiagent.session.stores.sqlite_store import (
    SQLiteSessionStore as LegacySQLiteSessionStoreModule,
)


def test_platform_persistence_session_is_canonical_home() -> None:
    """Platform session stores must be defined from platform-owned modules."""
    assert SessionStore is PlatformSessionStore
    assert LoadedSession is PlatformLoadedSession
    assert JsonlSessionStore is PlatformJsonlSessionStore
    assert SQLiteSessionStore is PlatformSQLiteSessionStore

    assert SessionStore.__module__ == "nano_multiagent.platform.persistence.session.base"
    assert LoadedSession.__module__ == "nano_multiagent.platform.persistence.session.base"
    assert JsonlSessionStore.__module__ == "nano_multiagent.platform.persistence.session.jsonl_store"
    assert SQLiteSessionStore.__module__ == "nano_multiagent.platform.persistence.session.sqlite_store"


def test_old_session_stores_shim_still_works() -> None:
    """Legacy session store modules must stay as compat shims to platform."""
    assert LegacySessionStore is PlatformSessionStore
    assert LegacyLoadedSession is PlatformLoadedSession
    assert LegacyJsonlSessionStore is PlatformJsonlSessionStore
    assert LegacySQLiteSessionStore is PlatformSQLiteSessionStore

    assert LegacySessionStoreBase is PlatformSessionStore
    assert LegacyLoadedSessionBase is PlatformLoadedSession
    assert LegacyJsonlSessionStoreModule is PlatformJsonlSessionStore
    assert LegacySQLiteSessionStoreModule is PlatformSQLiteSessionStore
