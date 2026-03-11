"""Canonical session event entry models and constructors."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence

from agent.core.ids import make_event_id


class SessionEntryKind(StrEnum):
    """Enumerate persisted session event kinds."""

    SESSION_CREATED = "session.created"
    TURN_APPENDED = "session.turn.appended"
    SESSION_ARCHIVED = "session.archived"
    COMPACTION = "session.compaction"
    RUN_STATUS = "session.run.status"



def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class SessionEntry:
    """Represent one generic session event record."""

    entry_id: str
    session_id: str
    created_at: str
    kind: SessionEntryKind
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompactionEntry:
    """Represent a compaction checkpoint plus summary payload."""

    entry_id: str
    session_id: str
    created_at: str
    first_kept_event_id: str
    summary: str
    data: Mapping[str, Any] = field(default_factory=dict)
    kind: SessionEntryKind = SessionEntryKind.COMPACTION


SessionEventEntry = SessionEntry | CompactionEntry


def new_session_created_entry(
    *,
    session_id: str,
    created_at: str | None = None,
    status: str = "active",
    entry_id: str | None = None,
    data: Mapping[str, Any] | None = None,
) -> SessionEntry:
    """Create a `session.created` event payload."""

    payload = {"status": status}
    if data:
        payload.update(data)
    return SessionEntry(
        entry_id=entry_id or make_event_id(),
        session_id=session_id,
        created_at=created_at or _utc_now_iso(),
        kind=SessionEntryKind.SESSION_CREATED,
        data=payload,
    )


def new_compaction_entry(
    *,
    session_id: str,
    first_kept_event_id: str,
    summary: str,
    created_at: str | None = None,
    entry_id: str | None = None,
    data: Mapping[str, Any] | None = None,
) -> CompactionEntry:
    """Create a compaction checkpoint event."""

    return CompactionEntry(
        entry_id=entry_id or make_event_id(),
        session_id=session_id,
        created_at=created_at or _utc_now_iso(),
        first_kept_event_id=first_kept_event_id,
        summary=summary,
        data=data or {},
    )


def new_turn_appended_entry(
    *,
    session_id: str,
    turn_id: str,
    role: str,
    content: str,
    message_id: str | None = None,
    parts: Sequence[Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
    created_at: str | None = None,
    entry_id: str | None = None,
) -> SessionEntry:
    """Create a turn-appended event with normalized parts/metadata containers."""

    payload: dict[str, Any] = {
        "turn_id": turn_id,
        "message_id": message_id,
        "role": role,
        "content": content,
        "parts": [dict(part) for part in parts or ()],
        "metadata": dict(metadata or {}),
    }
    return SessionEntry(
        entry_id=entry_id or make_event_id(),
        session_id=session_id,
        created_at=created_at or _utc_now_iso(),
        kind=SessionEntryKind.TURN_APPENDED,
        data=payload,
    )


def new_run_status_entry(
    *,
    session_id: str,
    run_id: str,
    status: str,
    turn_id: str | None = None,
    stop_reason: str | None = None,
    error: Mapping[str, Any] | None = None,
    created_at: str | None = None,
    entry_id: str | None = None,
    data: Mapping[str, Any] | None = None,
) -> SessionEntry:
    """Create a run-status event describing progress, stop reason, or failure."""

    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
    }
    if turn_id is not None:
        payload["turn_id"] = turn_id
    if stop_reason is not None:
        payload["stop_reason"] = stop_reason
    if error is not None:
        payload["error"] = dict(error)
    if data:
        payload.update(data)
    return SessionEntry(
        entry_id=entry_id or make_event_id(),
        session_id=session_id,
        created_at=created_at or _utc_now_iso(),
        kind=SessionEntryKind.RUN_STATUS,
        data=payload,
    )
