"""Verify core/session is the canonical home for shared session contracts."""

from agent.core.session import (
    CompactionEntry,
    LoadedSession,
    Session,
    SessionEntry,
    SessionEntryKind,
    SessionManager,
    SessionStore,
)
from agent.core.session.entries import CompactionEntry as CoreCompactionEntry
from agent.core.session.entries import SessionEntry as CoreSessionEntry
from agent.core.session.entries import SessionEntryKind as CoreSessionEntryKind
from agent.core.session.manager import SessionManager as CoreSessionManager
from agent.core.session.models import Session as CoreSession
from agent.core.session.store import LoadedSession as CoreLoadedSession
from agent.core.session.store import SessionStore as CoreSessionStore
from agent.platform.persistence.session.base import LoadedSession as PlatformLoadedSession
from agent.platform.persistence.session.base import SessionStore as PlatformSessionStore
from agent.core.session.entries import CompactionEntry as LegacyCompactionEntry
from agent.core.session.entries import SessionEntry as LegacySessionEntry
from agent.core.session.entries import SessionEntryKind as LegacySessionEntryKind
from agent.core.session.manager import SessionManager as LegacySessionManager
from agent.core.session.models import Session as LegacySession


def test_core_session_is_canonical_home() -> None:
    """Core session exports must originate from core-owned modules."""
    assert Session is CoreSession
    assert SessionEntry is CoreSessionEntry
    assert CompactionEntry is CoreCompactionEntry
    assert SessionEntryKind is CoreSessionEntryKind
    assert SessionManager is CoreSessionManager
    assert SessionStore is CoreSessionStore
    assert LoadedSession is CoreLoadedSession

    assert Session.__module__ == "agent.core.session.models"
    assert SessionEntry.__module__ == "agent.core.session.entries"
    assert CompactionEntry.__module__ == "agent.core.session.entries"
    assert SessionEntryKind.__module__ == "agent.core.session.entries"
    assert SessionManager.__module__ == "agent.core.session.manager"
    assert SessionStore.__module__ == "agent.core.session.store"
    assert LoadedSession.__module__ == "agent.core.session.store"


def test_old_session_paths_are_compat_shims() -> None:
    """Legacy session modules must re-export canonical core session objects."""
    assert LegacySession is CoreSession
    assert LegacySessionEntry is CoreSessionEntry
    assert LegacyCompactionEntry is CoreCompactionEntry
    assert LegacySessionEntryKind is CoreSessionEntryKind
    assert LegacySessionManager is CoreSessionManager

    assert PlatformSessionStore is CoreSessionStore
    assert PlatformLoadedSession is CoreLoadedSession
