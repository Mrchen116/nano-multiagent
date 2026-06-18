"""Canonical session aggregate manager built on JSONL event store."""

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.core import ids
from agent.core.utils.time import utc_now_iso as _utc_now_iso
from agent.core.types import Message

from .entries import (
    CompactionEntry,
    SessionEntry,
    new_compaction_entry,
    new_run_status_entry,
    new_session_created_entry,
    new_turn_appended_entry,
)
from .jsonl_store import (
    JsonlSessionStore,
    JsonlWriter,
    LoadResult,
    SessionConfig,
    SessionNotFoundError,
)
from .models import Session


class SessionManager:
    """Create/query/update sessions via JSONL append-only storage."""

    def __init__(self, *, store: JsonlSessionStore) -> None:
        self._store = store

    @property
    def writer(self) -> JsonlWriter:
        return self._store.writer

    @property
    def store(self) -> JsonlSessionStore:
        return self._store

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata: Mapping[str, Any] | None = None,
        parent_session_id: str | None = None,
    ) -> Session:
        """Create a new session and persist session_created line."""

        session_id = ids.make_session_id()
        created_at = _utc_now_iso()
        clean_metadata = dict(metadata or {})
        if title is not None:
            clean_metadata["title"] = title

        config = SessionConfig(
            session_id=session_id,
            created_at=created_at,
            workspace_root=workspace_root,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=clean_metadata,
        )
        self._store.create(session_id, config, parent_session_id=parent_session_id)

        return Session(
            session_id=session_id,
            status="active",
            created_at=created_at,
            workspace_root=workspace_root,
            system_prompt=system_prompt,
            skills=skills,
            tool_allowlist=tool_allowlist,
            metadata=clean_metadata,
        )

    def load(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> LoadResult:
        """Load raw config + messages from JSONL.

        ``workspace_root`` locates the session file; the stateless store cannot
        guess it. Omit it only when the store has a ``data_dir`` default base.
        """
        return self._store.load(
            session_id,
            workspace_root=workspace_root,
            parent_session_id=parent_session_id,
        )

    def get_session(
        self, session_id: str, *, workspace_root: Path | None = None
    ) -> Session | None:
        """Load session config from JSONL and return Session model."""

        try:
            result = self._store.load(session_id, workspace_root=workspace_root)
        except SessionNotFoundError:
            return None
        return _session_from_config(result.config)

    def list_sessions(
        self, *, limit: int, offset: int, workspace_root: Path | None = None
    ) -> tuple[tuple[Session, ...], bool]:
        """List sessions with pagination and `has_more` sentinel.

        Scoped to a single ``workspace_root`` — the stateless kernel has no
        cross-workspace session registry.
        """

        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

        pairs = self._store.list_session_ids_with_parents(
            limit=limit + 1, offset=offset, workspace_root=workspace_root
        )
        has_more = len(pairs) > limit
        sessions: list[Session] = []
        for sid, parent_id in pairs[:limit]:
            try:
                result = self._store.load(
                    sid, workspace_root=workspace_root, parent_session_id=parent_id
                )
                sessions.append(_session_from_config(result.config))
            except SessionNotFoundError:
                pass
        return tuple(sessions), has_more

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def append_turn_message(
        self,
        session_id: str,
        *,
        turn_id: str,
        role: str,
        content: str,
        message_id: str,
        parent_uuid: str | None = None,
        parts: Sequence[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
        workspace_root: Path | None = None,
    ) -> SessionEntry:
        """Append one turn message as a JSONL turn entry.

        ``parent_uuid`` links the entry into the conversation chain that
        ``JsonlSessionStore.load`` reconstructs by backtracking from the leaf.
        Leave it ``None`` only for a chain root; an out-of-band append to an
        existing session must pass the current tail's uuid, otherwise the entry
        is an unreachable orphan that load() silently drops (feat-394: cron
        awareness was persisted but never seen by later turns).

        ``workspace_root`` locates the session file.
        Returns a backward-compatible SessionEntry for callers that expect it.
        """

        entry: dict[str, Any] = {
            "type": "turn",
            "uuid": message_id,
            "parent_uuid": parent_uuid,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": _utc_now_iso(),
        }
        meta = dict(metadata or {})
        if meta.get("is_meta"):
            entry["is_meta"] = True
        if meta.get("is_compact_summary"):
            entry["is_compact_summary"] = True
        if meta.get("entrypoint"):
            entry["entrypoint"] = meta["entrypoint"]
        if parts:
            entry["parts"] = [dict(p) for p in parts]
        if meta.get("tool_calls"):
            entry["tool_calls"] = meta["tool_calls"]
        if meta.get("tool_call_id"):
            entry["tool_call_id"] = meta["tool_call_id"]

        self._store.append(session_id, entry, workspace_root=workspace_root)

        # Backward-compatible return value
        return new_turn_appended_entry(
            session_id=session_id,
            turn_id=turn_id,
            role=role,
            content=content,
            message_id=message_id,
            parts=parts,
            metadata=metadata,
        )

    def list_turn_messages(
        self, session_id: str, *, workspace_root: Path | None = None
    ) -> tuple[Message, ...]:
        """Materialize chat messages from JSONL, applying compact_boundary skip."""

        try:
            result = self._store.load(session_id, workspace_root=workspace_root)
        except SessionNotFoundError:
            return ()
        return tuple(result.messages)

    # ------------------------------------------------------------------
    # Compaction (backward-compatible adapter)
    # ------------------------------------------------------------------

    def append_compaction(
        self,
        session_id: str,
        *,
        first_kept_event_id: str,
        summary: str,
        data: Mapping[str, Any] | None = None,
        workspace_root: Path | None = None,
    ) -> CompactionEntry:
        """Persist compaction as compact_boundary + summary turn in JSONL.

        ``workspace_root`` locates the session file.
        Returns a backward-compatible CompactionEntry.
        """

        summary_uuid = ids.make_message_id()
        # 1. compact_boundary (marks the cut; turns after this are retained)
        self._store.append(
            session_id,
            {
                "type": "compact_boundary",
                "session_id": session_id,
                "timestamp": _utc_now_iso(),
                "summary_uuid": summary_uuid,
                "data": dict(data or {}),
            },
            workspace_root=workspace_root,
        )
        # 2. Summary turn (is_compact_summary + is_meta) — written AFTER boundary
        self._store.append(
            session_id,
            {
                "type": "turn",
                "uuid": summary_uuid,
                "parent_uuid": first_kept_event_id,
                "session_id": session_id,
                "role": "user",
                "content": summary,
                "timestamp": _utc_now_iso(),
                "is_meta": True,
                "is_compact_summary": True,
            },
            workspace_root=workspace_root,
        )

        # Backward-compatible return value
        return new_compaction_entry(
            session_id=session_id,
            first_kept_event_id=first_kept_event_id,
            summary=summary,
            data=data,
        )

    def list_entries(
        self, session_id: str, *, workspace_root: Path | None = None
    ) -> tuple[SessionEntry | CompactionEntry, ...]:
        """Return persisted events in backward-compatible SessionEntry format.

        This is a transitional adapter used by CompactionPlanner until M2
        refactors compaction to work directly on in-memory Message history.
        ``workspace_root`` locates the session file.
        """

        path = self._store.resolve_path(session_id, workspace_root=workspace_root)
        if not path.exists():
            return ()

        raw_lines: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # uuid -> turn entry lookup for compact_boundary resolution
        turn_by_uuid: dict[str, dict[str, Any]] = {
            line["uuid"]: line
            for line in raw_lines
            if line.get("type") == "turn" and "uuid" in line
        }

        entries: list[SessionEntry | CompactionEntry] = []
        for raw in raw_lines:
            etype = raw.get("type")
            if etype == "session_created":
                entries.append(
                    new_session_created_entry(
                        session_id=raw.get("session_id", session_id),
                        created_at=raw.get("created_at")
                        or raw.get("timestamp", _utc_now_iso()),
                        data=raw,
                    )
                )
            elif etype == "turn":
                entries.append(
                    new_turn_appended_entry(
                        session_id=raw.get("session_id", session_id),
                        turn_id=raw.get("turn_id", ""),
                        role=raw["role"],
                        content=raw["content"],
                        message_id=raw["uuid"],
                        metadata=_build_turn_metadata(raw),
                        created_at=raw.get("timestamp", _utc_now_iso()),
                    )
                )
            elif etype == "compact_boundary":
                summary_uuid = raw.get("summary_uuid")
                summary_text = ""
                if summary_uuid and summary_uuid in turn_by_uuid:
                    summary_text = turn_by_uuid[summary_uuid].get("content", "")
                entries.append(
                    new_compaction_entry(
                        session_id=raw.get("session_id", session_id),
                        first_kept_event_id="",
                        summary=summary_text,
                        data=raw.get("data", {}),
                        created_at=raw.get("timestamp", _utc_now_iso()),
                    )
                )
            elif etype == "config_update":
                entries.append(
                    new_session_created_entry(
                        session_id=raw.get("session_id", session_id),
                        created_at=raw.get("timestamp", _utc_now_iso()),
                        data=raw,
                    )
                )

        return tuple(entries)

    # ------------------------------------------------------------------
    # Transcript integrity
    # ------------------------------------------------------------------

    def prepare_transcript_for_run(
        self,
        session_id: str,
        *,
        reason: str = "interrupted",
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> None:
        """Ensure every assistant tool_call has a corresponding result before a run.

        Delegates to ``JsonlSessionStore.prepare_transcript_for_run``.
        """
        self._store.prepare_transcript_for_run(
            session_id,
            reason=reason,
            workspace_root=workspace_root,
            parent_session_id=parent_session_id,
        )

    def append_tool_call_recovery(
        self,
        session_id: str,
        *,
        tool_call_id: str,
        tool_name: str | None = None,
        reason: str,
        content: str | None = None,
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> None:
        """Append a single tool_call_recovery entry for an in-progress call.

        Lightweight eager path used by the runtime when a run ends with
        cancelled/aborted stop_reason.  Delegates to
        ``JsonlSessionStore.append_tool_call_recovery``. ``content`` (optional)
        overrides the synthetic tool-result body for user-attributed interrupts
        while leaving the badge ``reason`` intact (bugfix-417-M5, #114).
        """
        self._store.append_tool_call_recovery(
            session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            reason=reason,
            content=content,
            workspace_root=workspace_root,
            parent_session_id=parent_session_id,
        )

    # ------------------------------------------------------------------
    # Run status (no-op: RUN_STATUS is not persisted in JSONL)
    # ------------------------------------------------------------------

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
        """No-op in JSONL architecture: RUN_STATUS is memory-only via event hub.

        Returns a backward-compatible dummy SessionEntry.
        """

        return new_run_status_entry(
            session_id=session_id,
            run_id=run_id,
            status=status,
            turn_id=turn_id,
            stop_reason=stop_reason,
            error=error,
            data=data,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _session_from_config(config: SessionConfig) -> Session:
    metadata = dict(config.metadata)
    return Session(
        session_id=config.session_id,
        status="active",
        created_at=config.created_at,
        workspace_root=config.workspace_root,
        system_prompt=config.system_prompt,
        skills=config.skills,
        tool_allowlist=config.tool_allowlist,
        metadata=metadata,
    )


def _build_turn_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """Rebuild metadata dict from flattened JSONL turn fields."""

    meta: dict[str, Any] = {}
    for key in (
        "is_meta",
        "is_compact_summary",
        "is_provider_error",
        "entrypoint",
        "tool_calls",
        "tool_name",
        "tool_error",
        "tool_output",
    ):
        if key in raw:
            meta[key] = raw[key]
    if "tool_call_id" in raw:
        meta["tool_call_id"] = raw["tool_call_id"]
    if "parts" in raw:
        meta["parts"] = raw["parts"]
    if "reasoning_content" in raw:
        meta["reasoning_content"] = raw["reasoning_content"]
    if "reasoning_signature" in raw:
        meta["reasoning_signature"] = raw["reasoning_signature"]
    return meta
