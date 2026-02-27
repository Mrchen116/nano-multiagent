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
    new_session_created_entry,
    new_turn_appended_entry,
)
from .models import Session
from .stores.base import SessionStore


class SessionManager:
    def __init__(self, *, store: SessionStore) -> None:
        self._store = store

    def create_session(self, *, title: str | None = None, metadata: Mapping[str, Any] | None = None) -> Session:
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

    def list_entries(self, session_id: str) -> tuple[SessionEntry | CompactionEntry, ...]:
        loaded = self._store.load_session(session_id)
        if loaded is None:
            return ()
        return tuple(loaded.events)

    def list_turn_messages(self, session_id: str) -> tuple[Message, ...]:
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
