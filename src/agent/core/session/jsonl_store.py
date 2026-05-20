"""Canonical JSONL session store for the new session context storage architecture."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from agent.core.types import Message

from .jsonl_writer import JsonlWriter


class SessionNotFoundError(ValueError):
    """Raised when a session JSONL file does not exist."""


@dataclass(frozen=True)
class SessionConfig:
    """Resolved session configuration from session_created + config_updates."""

    session_id: str
    created_at: str
    workspace_root: Path
    system_prompt: str | None = None
    skills: tuple[str, ...] | None = None
    tool_allowlist: tuple[str, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadResult:
    """Result of loading a session from JSONL."""

    config: SessionConfig
    messages: list[Message]


class JsonlSessionStore:
    """Append-only JSONL session store with compact_boundary-aware resume.

    File layout:
        {data_dir}/sessions/{session_id}.jsonl
        {data_dir}/sessions/{parent_session_id}/subagents/{subagent_session_id}.jsonl
    """

    def __init__(self, *, data_dir: Path, writer: JsonlWriter | None = None) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._writer = writer or JsonlWriter()
        # agent_id -> list[(session_id, parent_session_id)] secondary index.
        # Rebuilt lazily on first metadata query.
        self._agent_index: dict[str, list[tuple[str, str | None]]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        session_id: str,
        config: SessionConfig,
        *,
        parent_session_id: str | None = None,
    ) -> None:
        """Write the session_created line for a new session (synchronous, immediate)."""

        path = self._resolve_path(session_id, parent_session_id=parent_session_id)
        entry = {
            "type": "session_created",
            "session_id": session_id,
            "created_at": config.created_at,
            "workspace_root": str(config.workspace_root),
        }
        if config.system_prompt is not None:
            entry["system_prompt"] = config.system_prompt
        if config.skills is not None:
            entry["skills"] = list(config.skills)
        if config.tool_allowlist is not None:
            entry["tool_allowlist"] = list(config.tool_allowlist)
        if config.metadata:
            entry["metadata"] = dict(config.metadata)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Incrementally update agent_id index if present.
        agent_id = config.metadata.get("agent_id") if config.metadata else None
        if isinstance(agent_id, str) and agent_id:
            if self._agent_index is not None:
                self._agent_index.setdefault(agent_id, []).append((session_id, parent_session_id))

    def append(self, session_id: str, entry: dict, *, parent_session_id: str | None = None) -> None:
        """Enqueue one JSONL entry for background flush."""

        path = self._resolve_path(session_id, parent_session_id=parent_session_id)
        self._writer.enqueue(path, entry)

    def load(self, session_id: str, *, parent_session_id: str | None = None) -> LoadResult:
        """Load session config and message chain from JSONL.

        Handles compact_boundary skip and parent_uuid backtracking.
        Raises SessionNotFoundError when the file does not exist.
        """

        path = self._resolve_path(session_id, parent_session_id=parent_session_id)
        if not path.exists():
            raise SessionNotFoundError(session_id)

        config: dict[str, Any] = {}
        raw_lines: list[dict] = []

        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw_lines.append(json.loads(line))

        # First pass: extract config and find latest compact_boundary index
        boundary_idx = -1
        for i, entry in enumerate(raw_lines):
            etype = entry["type"]
            if etype == "session_created":
                config = _extract_config(entry)
            elif etype == "config_update":
                config = _merge_config(config, entry)
            elif etype == "compact_boundary":
                boundary_idx = i

        # Only keep turns after the latest compact_boundary
        if boundary_idx >= 0:
            turns = [entry for entry in raw_lines[boundary_idx + 1:] if entry.get("type") == "turn"]
        else:
            turns = [entry for entry in raw_lines if entry.get("type") == "turn"]

        if not turns:
            return LoadResult(config=_to_session_config(session_id, config), messages=[])

        # Build uuid -> entry mapping
        entry_by_uuid: dict[str, dict] = {t["uuid"]: t for t in turns}

        # Find terminals: uuids not referenced as any parent_uuid
        all_parent_uuids = {t.get("parent_uuid") for t in turns if t.get("parent_uuid")}
        terminals = [t for t in turns if t["uuid"] not in all_parent_uuids]

        # Normal case: single terminal; with branches take latest by timestamp
        leaf = max(terminals, key=lambda t: t.get("timestamp", ""))

        # Backtrack via parent_uuid to root
        chain: list[dict] = []
        seen: set[str] = set()
        current: dict | None = leaf
        while current is not None:
            chain.append(current)
            seen.add(current["uuid"])
            parent_uuid = current.get("parent_uuid")
            current = entry_by_uuid.get(parent_uuid) if parent_uuid else None

        # If no parent_uuid links exist (backward-compatible flat turns),
        # fall back to chronological order of all turns.
        has_links = any(t.get("parent_uuid") in entry_by_uuid for t in turns)
        if not has_links:
            chain = sorted(turns, key=lambda t: t.get("timestamp", ""))
            messages = [_to_message(t) for t in chain]
            return LoadResult(config=_to_session_config(session_id, config), messages=messages)

        chain.reverse()

        # Multi-pass recovery: collect orphaned children whose parent is in the
        # seen set and whose group_id matches an active group on the chain.
        # This handles parallel tool results that all point to the same assistant
        # parent (the linked-list walk only keeps one branch) while avoiding
        # resurrection of dead branches from a previous rewind.
        active_groups: set[str] = {
            t["group_id"] for t in chain if t.get("group_id")
        }
        while True:
            newly_found = False
            for turn in turns:
                if turn["uuid"] in seen:
                    continue
                parent_uuid = turn.get("parent_uuid")
                group_id = turn.get("group_id")
                if (
                    parent_uuid
                    and parent_uuid in seen
                    and group_id
                    and group_id in active_groups
                ):
                    seen.add(turn["uuid"])
                    newly_found = True
            if not newly_found:
                break

        chain_uuids = {e["uuid"] for e in chain}
        all_entries = chain + [t for t in turns if t["uuid"] in seen and t["uuid"] not in chain_uuids]
        all_entries.sort(key=lambda t: t.get("timestamp", ""))

        messages = [_to_message(t) for t in all_entries]
        return LoadResult(config=_to_session_config(session_id, config), messages=messages)

    def update_config(self, session_id: str, **fields: Any) -> None:
        """Append a config_update line and return the merged config."""

        path = self._resolve_path(session_id)
        entry: dict[str, Any] = {
            "type": "config_update",
            "session_id": session_id,
            "timestamp": _utc_now_iso(),
        }
        for key in ("system_prompt", "skills", "tool_allowlist", "metadata"):
            if key in fields and fields[key] is not None:
                entry[key] = fields[key]
        self._writer.enqueue(path, entry)

    def list_session_ids(self, *, limit: int, offset: int) -> tuple[str, ...]:
        """List session ids by most recent mtime (main + subagent)."""

        main_files = self._data_dir.glob("sessions/*.jsonl")
        subagent_files = self._data_dir.glob("sessions/*/subagents/*.jsonl")
        all_files = sorted(
            (*main_files, *subagent_files),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return tuple(p.stem for p in all_files[offset : offset + limit])

    def list_session_ids_with_parents(
        self, *, limit: int, offset: int
    ) -> tuple[tuple[str, str | None], ...]:
        """List (session_id, parent_session_id) pairs by most recent mtime."""

        main_files = self._data_dir.glob("sessions/*.jsonl")
        subagent_files = self._data_dir.glob("sessions/*/subagents/*.jsonl")
        all_files = sorted(
            (*main_files, *subagent_files),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        result = []
        for p in all_files[offset : offset + limit]:
            parent = self._infer_parent_from_path(p)
            result.append((p.stem, parent))
        return tuple(result)

    @property
    def writer(self) -> JsonlWriter:
        return self._writer

    def resolve_path(self, session_id: str, *, parent_session_id: str | None = None) -> Path:
        return self._resolve_path(session_id, parent_session_id=parent_session_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_path(self, session_id: str, *, parent_session_id: str | None = None) -> Path:
        if parent_session_id:
            return self._data_dir / "sessions" / parent_session_id / "subagents" / f"{session_id}.jsonl"
        return self._data_dir / "sessions" / f"{session_id}.jsonl"

    def find_session_by_metadata(
        self,
        *,
        parent_session_id: str | None,
        match: Mapping[str, Any],
    ) -> str | None:
        """Return session_id whose metadata matches all key/value pairs in ``match``.

        Used by background tasks to resolve agent_id → runtime session_id when
        the in-memory mapping has been lost (kernel restart, parent agent resume).
        """
        if self._agent_index is None:
            self._build_agent_index()

        agent_id = match.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            return None

        results = self._agent_index.get(agent_id) if self._agent_index else None
        if not results:
            return None

        for found_session_id, found_parent in results:
            if parent_session_id is not None and found_parent != parent_session_id:
                continue
            return found_session_id
        return None

    def _build_agent_index(self) -> None:
        """Scan all session files and rebuild agent_id → session_id index."""
        self._agent_index = {}
        sessions_dir = self._data_dir / "sessions"
        for path in sessions_dir.glob("*.jsonl"):
            session_id = path.stem
            parent_id = self._infer_parent_from_path(path)
            agent_id = self._read_agent_id_from_file(path)
            if agent_id:
                self._agent_index.setdefault(agent_id, []).append((session_id, parent_id))
        for path in sessions_dir.glob("*/subagents/*.jsonl"):
            session_id = path.stem
            parent_id = self._infer_parent_from_path(path)
            agent_id = self._read_agent_id_from_file(path)
            if agent_id:
                self._agent_index.setdefault(agent_id, []).append((session_id, parent_id))

    @staticmethod
    def _infer_parent_from_path(path: Path) -> str | None:
        parts = path.parts
        try:
            subagents_idx = parts.index("subagents")
            if subagents_idx >= 2:
                return parts[subagents_idx - 1]
        except ValueError:
            pass
        return None

    @staticmethod
    def _read_agent_id_from_file(path: Path) -> str | None:
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") == "session_created":
                        metadata = entry.get("metadata")
                        if isinstance(metadata, dict):
                            agent_id = metadata.get("agent_id")
                            if isinstance(agent_id, str) and agent_id:
                                return agent_id
                        return None
                    # Only check the first non-empty line.
                    return None
        except (OSError, ValueError):
            return None
        return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _extract_config(entry: dict[str, Any]) -> dict[str, Any]:
    """Extract config fields from a session_created or config_update entry."""

    config: dict[str, Any] = {}
    for key in ("workspace_root", "system_prompt", "skills", "tool_allowlist", "metadata", "created_at"):
        if key in entry:
            config[key] = entry[key]
    return config


def _merge_config(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Merge a config_update into the base config."""

    merged = dict(base)
    for key in ("system_prompt", "skills", "tool_allowlist", "metadata"):
        if key in update:
            merged[key] = update[key]
    return merged


def _to_session_config(session_id: str, config: dict[str, Any]) -> SessionConfig:
    raw_root = config.get("workspace_root")
    workspace_root = Path(str(raw_root)) if isinstance(raw_root, str) and raw_root.strip() else Path.cwd()

    raw_sp = config.get("system_prompt")
    system_prompt = raw_sp if isinstance(raw_sp, str) and raw_sp.strip() else None

    raw_skills = config.get("skills")
    skills: tuple[str, ...] | None = (
        tuple(s for s in raw_skills if isinstance(s, str)) if isinstance(raw_skills, list) else None
    )

    raw_allowlist = config.get("tool_allowlist")
    tool_allowlist: tuple[str, ...] | None = (
        tuple(s for s in raw_allowlist if isinstance(s, str)) if isinstance(raw_allowlist, list) else None
    )

    metadata = config.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return SessionConfig(
        session_id=session_id,
        created_at=config.get("created_at", _utc_now_iso()),
        workspace_root=workspace_root,
        system_prompt=system_prompt,
        skills=skills,
        tool_allowlist=tool_allowlist,
        metadata=metadata,
    )


def _to_message(entry: dict[str, Any]) -> Message:
    return Message(
        message_id=str(entry["uuid"]),
        role=str(entry["role"]),
        content=entry["content"],
        parent_message_id=entry.get("parent_uuid"),
        group_id=entry.get("group_id"),
        tool_call_id=entry.get("tool_call_id"),
        metadata=_extract_message_metadata(entry),
        reasoning_content=entry.get("reasoning_content") or None,
        reasoning_signature=entry.get("reasoning_signature") or None,
    )


def _extract_message_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata fields from a JSONL turn entry."""

    meta: dict[str, Any] = {}
    for key in ("is_meta", "is_compact_summary", "entrypoint"):
        if key in entry:
            meta[key] = entry[key]
    # tool_calls from assistant metadata
    if "tool_calls" in entry:
        meta["tool_calls"] = entry["tool_calls"]
    return meta
