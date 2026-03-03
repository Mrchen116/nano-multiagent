"""In-process registry for session usage snapshots produced by built-in hooks."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable


@dataclass(frozen=True, slots=True)
class SessionUsageSnapshot:
    """Exact session usage counters aggregated from provider usage payloads."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    last_prompt_tokens: int
    last_completion_tokens: int
    last_total_tokens: int
    turn_count: int


_SnapshotReader = Callable[[str], SessionUsageSnapshot | None]
_reader_lock = Lock()
_snapshot_reader: _SnapshotReader | None = None


def register_session_usage_reader(reader: _SnapshotReader) -> None:
    """Register active in-process session usage reader."""
    global _snapshot_reader
    with _reader_lock:
        _snapshot_reader = reader


def clear_session_usage_reader() -> None:
    """Clear active in-process session usage reader."""
    global _snapshot_reader
    with _reader_lock:
        _snapshot_reader = None


def get_session_usage_snapshot(session_id: str) -> SessionUsageSnapshot | None:
    """Return exact usage snapshot for one session when available."""
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    with _reader_lock:
        reader = _snapshot_reader
    if reader is None:
        return None
    return reader(session_id.strip())
