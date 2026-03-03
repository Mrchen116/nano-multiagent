"""Serialization helpers for session events and snapshots."""

from typing import Any, Mapping

from .entries import CompactionEntry, SessionEntry, SessionEntryKind, SessionEventEntry

ENTRY_SERIALIZATION_VERSION = 1
SNAPSHOT_SERIALIZATION_VERSION = 1


def serialize_entry(entry: SessionEventEntry) -> dict[str, Any]:
    """Serialize one session event entry into persisted JSON payload."""

    payload: dict[str, Any] = {
        "version": ENTRY_SERIALIZATION_VERSION,
        "entry_id": entry.entry_id,
        "session_id": entry.session_id,
        "created_at": entry.created_at,
        "kind": entry.kind.value,
        "data": dict(entry.data),
    }
    if isinstance(entry, CompactionEntry):
        payload["first_kept_event_id"] = entry.first_kept_event_id
        payload["summary"] = entry.summary
    return payload


def deserialize_entry(payload: Mapping[str, Any]) -> SessionEventEntry:
    """Deserialize one persisted event payload with strict version checks."""

    # PERSISTENCE PROTOCOL: version mismatch must fail fast to avoid silently
    # replaying incompatible on-disk history with corrupted semantics.
    version = int(payload["version"])
    if version != ENTRY_SERIALIZATION_VERSION:
        raise ValueError(f"unsupported session entry version: {version}")

    kind = SessionEntryKind(payload["kind"])
    common = {
        "entry_id": str(payload["entry_id"]),
        "session_id": str(payload["session_id"]),
        "created_at": str(payload["created_at"]),
        "data": dict(payload.get("data", {})),
    }
    if kind is SessionEntryKind.COMPACTION:
        return CompactionEntry(
            **common,
            first_kept_event_id=str(payload["first_kept_event_id"]),
            summary=str(payload["summary"]),
        )
    return SessionEntry(kind=kind, **common)


def serialize_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize session snapshot state with protocol version metadata."""

    return {
        "version": SNAPSHOT_SERIALIZATION_VERSION,
        "state": dict(snapshot),
    }


def deserialize_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Deserialize snapshot payload with strict version enforcement."""

    version = int(payload["version"])
    if version != SNAPSHOT_SERIALIZATION_VERSION:
        raise ValueError(f"unsupported session snapshot version: {version}")
    return dict(payload.get("state", {}))
