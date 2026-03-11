"""Canonical shared session models, events, manager, and store contract."""

from .entries import (
    CompactionEntry,
    SessionEntry,
    SessionEntryKind,
    SessionEventEntry,
    new_compaction_entry,
    new_run_status_entry,
    new_session_created_entry,
    new_turn_appended_entry,
)
from .manager import SessionManager
from .models import Session
from .store import LoadedSession, SessionStore

__all__ = [
    "CompactionEntry",
    "LoadedSession",
    "Session",
    "SessionEntry",
    "SessionEntryKind",
    "SessionEventEntry",
    "SessionManager",
    "SessionStore",
    "new_compaction_entry",
    "new_run_status_entry",
    "new_session_created_entry",
    "new_turn_appended_entry",
]
