"""Compatibility shim for canonical platform session usage contracts."""

from nano_multiagent.platform.hooks.session_usage import (
    SESSION_USAGE_SNAPSHOT_READER_STATE_KEY,
    SessionUsageSnapshot,
    SessionUsageSnapshotReader,
    get_session_usage_snapshot,
    set_session_usage_snapshot_reader,
)

__all__ = [
    "SESSION_USAGE_SNAPSHOT_READER_STATE_KEY",
    "SessionUsageSnapshot",
    "SessionUsageSnapshotReader",
    "get_session_usage_snapshot",
    "set_session_usage_snapshot_reader",
]
