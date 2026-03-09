"""Verify core/session is the canonical home for shared session contracts."""

from nano_multiagent.core.session import (
    CompactionEntry,
    LoadedSession,
    Session,
    SessionEntry,
    SessionEntryKind,
    SessionManager,
    SessionStore,
)
from nano_multiagent.core.session.entries import CompactionEntry as CoreCompactionEntry
from nano_multiagent.core.session.entries import SessionEntry as CoreSessionEntry
from nano_multiagent.core.session.entries import SessionEntryKind as CoreSessionEntryKind
from nano_multiagent.core.session.manager import SessionManager as CoreSessionManager
from nano_multiagent.core.session.models import Session as CoreSession
from nano_multiagent.core.session.store import LoadedSession as CoreLoadedSession
from nano_multiagent.core.session.store import SessionStore as CoreSessionStore
from nano_multiagent.platform.persistence.session.base import LoadedSession as PlatformLoadedSession
from nano_multiagent.platform.persistence.session.base import SessionStore as PlatformSessionStore
from nano_multiagent.session.entries import CompactionEntry as LegacyCompactionEntry
from nano_multiagent.session.entries import SessionEntry as LegacySessionEntry
from nano_multiagent.session.entries import SessionEntryKind as LegacySessionEntryKind
from nano_multiagent.session.manager import SessionManager as LegacySessionManager
from nano_multiagent.session.models import Session as LegacySession


def test_core_session_is_canonical_home() -> None:
    """Core session exports must originate from core-owned modules."""
    assert Session is CoreSession
    assert SessionEntry is CoreSessionEntry
    assert CompactionEntry is CoreCompactionEntry
    assert SessionEntryKind is CoreSessionEntryKind
    assert SessionManager is CoreSessionManager
    assert SessionStore is CoreSessionStore
    assert LoadedSession is CoreLoadedSession

    assert Session.__module__ == "nano_multiagent.core.session.models"
    assert SessionEntry.__module__ == "nano_multiagent.core.session.entries"
    assert CompactionEntry.__module__ == "nano_multiagent.core.session.entries"
    assert SessionEntryKind.__module__ == "nano_multiagent.core.session.entries"
    assert SessionManager.__module__ == "nano_multiagent.core.session.manager"
    assert SessionStore.__module__ == "nano_multiagent.core.session.store"
    assert LoadedSession.__module__ == "nano_multiagent.core.session.store"


def test_old_session_paths_are_compat_shims() -> None:
    """Legacy session modules must re-export canonical core session objects."""
    assert LegacySession is CoreSession
    assert LegacySessionEntry is CoreSessionEntry
    assert LegacyCompactionEntry is CoreCompactionEntry
    assert LegacySessionEntryKind is CoreSessionEntryKind
    assert LegacySessionManager is CoreSessionManager

    assert PlatformSessionStore is CoreSessionStore
    assert PlatformLoadedSession is CoreLoadedSession
