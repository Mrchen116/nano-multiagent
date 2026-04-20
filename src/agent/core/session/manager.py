"""Canonical session aggregate manager built on event store plus optional snapshots."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.core import ids
from agent.core.types import Message

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

    def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Session:
        """Create a new active session and persist both event and initial snapshot."""

        session_id = ids.make_session_id()
        created_at = datetime.now(UTC).isoformat()
        extra_data: dict[str, Any] = {"workspace_root": str(workspace_root)}
        if title is not None:
            extra_data["title"] = title
        if system_prompt is not None:
            extra_data["system_prompt"] = system_prompt
        if skills is not None:
            extra_data["skills"] = list(skills)
        if tool_allowlist is not None:
            extra_data["tool_allowlist"] = list(tool_allowlist)
        if metadata:
            extra_data["metadata"] = dict(metadata)
        event = new_session_created_entry(
            session_id=session_id,
            created_at=created_at,
            status="active",
            data=extra_data,
        )
        self._store.append_event(session_id, event)
        session = Session(
            session_id=session_id,
            status="active",
            created_at=created_at,
            workspace_root=workspace_root,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=dict(metadata or {}),
        )
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
        """Materialize chat messages, applying compaction summary semantics.

        When a CompactionEntry exists, all TURN_APPENDED events before it are
        dropped (replaced by the summary + restored files). Only events after
        the latest CompactionEntry are retained as original messages.
        """

        loaded = self._store.load_session(session_id)
        if loaded is None:
            return ()

        # Find the latest CompactionEntry by index (entry_id is not sortable).
        latest_compaction_idx = -1
        for i, entry in enumerate(loaded.events):
            if isinstance(entry, CompactionEntry):
                latest_compaction_idx = i

        # Collect only TURN_APPENDED events after the latest compaction.
        messages: list[Message] = []
        for entry in loaded.events[latest_compaction_idx + 1:]:
            if entry.kind is not SessionEntryKind.TURN_APPENDED:
                continue
            message = self._message_from_turn_event(entry)
            if message is not None:
                messages.append(message)

        if latest_compaction_idx >= 0:
            latest_compaction = loaded.events[latest_compaction_idx]
            from agent.core.agent.compaction.prompts import get_compact_user_summary_message

            # 1. Summary user message (insert at front)
            summary_content = get_compact_user_summary_message(latest_compaction.summary)
            summary_message = Message(
                message_id=f"{latest_compaction.entry_id}:summary",
                role="user",
                content=summary_content,
                metadata={"compaction_summary": True},
            )
            messages.insert(0, summary_message)

            # 2. Restored files user message (after summary)
            restored_files = latest_compaction.data.get("restored_files", [])
            if restored_files:
                files_content = "\n\n".join(restored_files)
                files_message = Message(
                    message_id=f"{latest_compaction.entry_id}:files",
                    role="user",
                    content=files_content,
                    metadata={"compaction_files": True},
                )
                messages.insert(1, files_message)

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
        metadata = snapshot.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}
        workspace_root, system_prompt, skills, tool_allowlist = _parse_session_fields(snapshot, metadata)
        # Strip promoted fields from pass-through metadata so they are not duplicated.
        clean_metadata = {
            k: v for k, v in dict(metadata).items()
            if k not in {"workspace_root", "system_prompt", "skills", "tool_allowlist"}
        }
        return Session(
            session_id=str(snapshot["session_id"]),
            status=status,
            created_at=str(snapshot["created_at"]),
            workspace_root=workspace_root,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=clean_metadata,
        )

    def _apply_event(self, session: Session | None, entry: SessionEntry | CompactionEntry) -> Session | None:
        if isinstance(entry, CompactionEntry):
            return session

        if entry.kind is SessionEntryKind.SESSION_CREATED:
            status = str(entry.data.get("status", "active"))
            metadata = entry.data.get("metadata")
            if not isinstance(metadata, Mapping):
                metadata = {}
            workspace_root, system_prompt, skills, tool_allowlist = _parse_session_fields(entry.data, metadata)
            clean_metadata = {
                k: v for k, v in dict(metadata).items()
                if k not in {"workspace_root", "system_prompt", "skills", "tool_allowlist"}
            }
            return Session(
                session_id=entry.session_id,
                status=status,
                created_at=entry.created_at,
                workspace_root=workspace_root,
                system_prompt=system_prompt,
                skills=skills,
                tool_allowlist=tool_allowlist,
                metadata=clean_metadata,
            )
        if entry.kind is SessionEntryKind.SESSION_ARCHIVED and session is not None:
            return replace(session, status="archived")
        return session

    def _to_snapshot(self, session: Session) -> dict[str, Any]:
        snap: dict[str, Any] = {
            "session_id": session.session_id,
            "status": session.status,
            "created_at": session.created_at,
            "workspace_root": str(session.workspace_root),
            "metadata": dict(session.metadata),
        }
        if session.system_prompt is not None:
            snap["system_prompt"] = session.system_prompt
        if session.skills is not None:
            snap["skills"] = list(session.skills)
        if session.tool_allowlist is not None:
            snap["tool_allowlist"] = list(session.tool_allowlist)
        return snap

    def _message_from_turn_event(self, entry: SessionEntry) -> Message | None:
        message_id = entry.data.get("message_id")
        role = entry.data.get("role")
        content = entry.data.get("content")
        if not isinstance(message_id, str) or not isinstance(role, str):
            return None
        if not isinstance(content, str) and not isinstance(content, list):
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


def _parse_session_fields(
    data: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[Path, str | None, tuple[str, ...] | None, tuple[str, ...] | None]:
    """Extract typed session fields from a snapshot or event data dict.

    Supports both the new format (fields at top level of ``data``) and the old
    format (fields inside ``data["metadata"]``) for backward compatibility with
    existing SQLite snapshots.

    Returns:
        (workspace_root, system_prompt, skills, tool_allowlist)
    """
    # workspace_root: top-level (new) or metadata (old).
    raw_root = data.get("workspace_root")
    if raw_root is None:
        raw_root = metadata.get("workspace_root")
    workspace_root = Path(str(raw_root)) if isinstance(raw_root, str) and raw_root.strip() else Path.cwd()

    # system_prompt: top-level or metadata fallback.
    raw_sp = data.get("system_prompt")
    if raw_sp is None:
        raw_sp = metadata.get("system_prompt")
    system_prompt: str | None = raw_sp if isinstance(raw_sp, str) and raw_sp.strip() else None

    # skills: top-level or metadata fallback.
    raw_skills = data.get("skills")
    if raw_skills is None:
        raw_skills = metadata.get("skills")
    skills: tuple[str, ...] | None = (
        tuple(s for s in raw_skills if isinstance(s, str)) if isinstance(raw_skills, list) else None
    )

    # tool_allowlist: top-level or metadata fallback.
    raw_allowlist = data.get("tool_allowlist")
    if raw_allowlist is None:
        raw_allowlist = metadata.get("tool_allowlist")
    tool_allowlist: tuple[str, ...] | None = (
        tuple(s for s in raw_allowlist if isinstance(s, str)) if isinstance(raw_allowlist, list) else None
    )

    return workspace_root, system_prompt, skills, tool_allowlist
