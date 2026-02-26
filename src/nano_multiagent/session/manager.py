from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Mapping

from nano_multiagent.core import ids

from .entries import CompactionEntry, SessionEntry, SessionEntryKind, new_session_created_entry
from .models import Session
from .stores.base import SessionStore


class SessionManager:
    def __init__(self, *, store: SessionStore) -> None:
        self._store = store

    def create_session(self) -> Session:
        session_id = ids.make_session_id()
        created_at = datetime.now(UTC).isoformat()
        event = new_session_created_entry(
            session_id=session_id,
            created_at=created_at,
            status="active",
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
