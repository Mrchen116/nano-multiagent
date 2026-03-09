"""Canonical session aggregate manager built on event store plus optional snapshots."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from nano_multiagent.core import ids
from nano_multiagent.core.types import Message

from .entries import (
    CompactionEntry,
    SessionEntry,
    SessionEntryKind,
    new_compaction_entry,
    new_run_status_entry,
    new_session_created_entry,
    new_turn_appended_entry,
)
from .models import Session
from .store import SessionStore


class SessionManager:
    """Create/query/update sessions by appending immutable session events."""

    def __init__(self, *, store: SessionStore) -> None:
        self._store = store

    def create_session(self, *, title: str | None = None, metadata: Mapping[str, Any] | None = None) -> Session:
        """Create a new active session and persist both event and initial snapshot."""

        session_id = ids.make_session_id()
        created_at = datetime.now(UTC).isoformat()
        extra_data: dict[str, Any] = {}
        if title is not None:
            extra_data["title"] = title
        if metadata:
            extra_data["metadata"] = dict(metadata)
        event = new_session_created_entry(
            session_id=session_id,
            created_at=created_at,
            status="active",
            data=extra_data,
        )
        self._store.append_event(session_id, event)
        session = Session(session_id=session_id, status="active", created_at=created_at)
        self._store.save_snapshot(session_id, self._to_snapshot(session))
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Rebuild a session from snapshot + ordered events."""

        loaded = self._store.load_session(session_id)
        if loaded is None:
            return None

        session = self._from_snapshot(loaded.snapshot)
        for entry in loaded.events:
            session = self._apply_event(session, entry)
        return session

    def append_turn_message(
        self,
        session_id: str,
        *,
        turn_id: str,
        role: str,
        content: str,
        message_id: str,
        parts: Sequence[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> SessionEntry:
        """Append one turn message event for an existing session."""

        if self.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")
        entry = new_turn_appended_entry(
            session_id=session_id,
            turn_id=turn_id,
            role=role,
            content=content,
            message_id=message_id,
            parts=parts,
            metadata=metadata,
        )
        self._store.append_event(session_id, entry)
        return entry

    def append_compaction(
        self,
        session_id: str,
        *,
        first_kept_event_id: str,
        summary: str,
        data: Mapping[str, Any] | None = None,
    ) -> CompactionEntry:
        """Append a compaction checkpoint event for an existing session."""

        if self.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")
        entry = new_compaction_entry(
            session_id=session_id,
            first_kept_event_id=first_kept_event_id,
            summary=summary,
            data=data,
        )
        self._store.append_event(session_id, entry)
        return entry

    def append_run_status(
        self,
        session_id: str,
        *,
        run_id: str,
        status: str,
        turn_id: str | None = None,
        stop_reason: str | None = None,
        error: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> SessionEntry:
        """Append one run status event for an existing session."""

        if self.get_session(session_id) is None:
            raise ValueError(f"session does not exist: {session_id}")
        entry = new_run_status_entry(
            session_id=session_id,
            run_id=run_id,
            status=status,
            turn_id=turn_id,
            stop_reason=stop_reason,
            error=error,
            data=data,
        )
        self._store.append_event(session_id, entry)
        return entry

    def list_entries(self, session_id: str) -> tuple[SessionEntry | CompactionEntry, ...]:
        """Return persisted events for one session in store order."""

        loaded = self._store.load_session(session_id)
        if loaded is None:
            return ()
        return tuple(loaded.events)

    def list_turn_messages(self, session_id: str) -> tuple[Message, ...]:
        """Materialize chat messages, applying compaction summary semantics."""

        loaded = self._store.load_session(session_id)
        if loaded is None:
            return ()

        latest_compaction: CompactionEntry | None = None
        for entry in loaded.events:
            if isinstance(entry, CompactionEntry):
                latest_compaction = entry

        messages: list[Message] = []
        collecting_kept_messages = latest_compaction is None
        for entry in loaded.events:
            if isinstance(entry, CompactionEntry):
                continue
            if entry.kind is not SessionEntryKind.TURN_APPENDED:
                continue
            if (
                latest_compaction is not None
                and not collecting_kept_messages
                and entry.entry_id == latest_compaction.first_kept_event_id
            ):
                collecting_kept_messages = True
            if not collecting_kept_messages:
                continue
            # Compaction boundary: only messages at/after first_kept_event_id are replayed.
            message = self._message_from_turn_event(entry)
            if message is not None:
                messages.append(message)

        if latest_compaction is not None:
            summary_message = Message(
                message_id=f"{latest_compaction.entry_id}:summary",
                role="system",
                content=latest_compaction.summary,
                metadata={
                    "compaction_entry_id": latest_compaction.entry_id,
                    "first_kept_event_id": latest_compaction.first_kept_event_id,
                },
            )
            messages.insert(0, summary_message)
        return tuple(messages)

    def list_sessions(self, *, limit: int, offset: int) -> tuple[tuple[Session, ...], bool]:
        """List sessions with pagination and `has_more` sentinel."""

        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

        list_ids = getattr(self._store, "list_session_ids", None)
        if not callable(list_ids):
            return (), False

        session_ids = tuple(list_ids(limit=limit + 1, offset=offset))
        has_more = len(session_ids) > limit
        sessions: list[Session] = []
        for session_id in session_ids[:limit]:
            session = self.get_session(session_id)
            if session is not None:
                sessions.append(session)
        return tuple(sessions), has_more

    def _from_snapshot(self, snapshot: Mapping[str, Any] | None) -> Session | None:
        if snapshot is None:
            return None
        if "session_id" not in snapshot or "created_at" not in snapshot:
            return None
        status = str(snapshot.get("status", "active"))
        return Session(
            session_id=str(snapshot["session_id"]),
            status=status,
            created_at=str(snapshot["created_at"]),
        )

    def _apply_event(self, session: Session | None, entry: SessionEntry | CompactionEntry) -> Session | None:
        if isinstance(entry, CompactionEntry):
            return session

        if entry.kind is SessionEntryKind.SESSION_CREATED:
            status = str(entry.data.get("status", "active"))
            return Session(
                session_id=entry.session_id,
                status=status,
                created_at=entry.created_at,
            )
        if entry.kind is SessionEntryKind.SESSION_ARCHIVED and session is not None:
            return replace(session, status="archived")
        return session

    def _to_snapshot(self, session: Session) -> dict[str, str]:
        return {
            "session_id": session.session_id,
            "status": session.status,
            "created_at": session.created_at,
        }

    def _message_from_turn_event(self, entry: SessionEntry) -> Message | None:
        message_id = entry.data.get("message_id")
        role = entry.data.get("role")
        content = entry.data.get("content")
        if not isinstance(message_id, str) or not isinstance(role, str) or not isinstance(content, str):
            return None
        metadata = entry.data.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}
        return Message(
            message_id=message_id,
            role=role,
            content=content,
            metadata=dict(metadata),
        )
