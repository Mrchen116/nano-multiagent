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

    The store is **stateless** with respect to session location: it never holds
    or persists a ``session_id -> workspace_root`` mapping.  Every method that
    must locate a session file accepts the session's ``workspace_root`` from the
    caller and resolves the path on the spot:

        {workspace_root}/.nano/sessions/{session_id}.jsonl
        {workspace_root}/.nano/sessions/{parent_session_id}/subagents/{subagent_session_id}.jsonl

    This is the deliberate fix for the feat-330 chicken-and-egg gap: ``workspace_root``
    lives *inside* each session file, so locating a file by ``session_id`` alone is
    impossible.  The kernel stays stateless; the gateway and CLI — which already
    know each session's ``workspace_root`` (PA from its per-agent config, CLI from
    its working directory) — pass it on every request.

    Backward compatibility: ``data_dir`` is an optional default base.  When a call
    omits ``workspace_root`` and ``data_dir`` was provided at construction, paths
    resolve under ``data_dir`` (the legacy flat layout).  Production bootstrap
    constructs the store with ``data_dir=None``, so production callers must always
    pass ``workspace_root``.
    """

    def __init__(self, *, data_dir: Path | None, writer: JsonlWriter | None = None) -> None:
        if data_dir is not None:
            self._data_dir: Path | None = Path(data_dir)
            self._data_dir.mkdir(parents=True, exist_ok=True)
        else:
            # No default base — callers must pass workspace_root on every call.
            self._data_dir = None
        self._writer = writer or JsonlWriter()

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
        """Write the session_created line for a new session (synchronous, immediate).

        The session's ``workspace_root`` comes from ``config``; the caller does
        not pass it separately here because ``SessionConfig`` already carries it.
        """

        path = self._resolve_path(
            session_id,
            workspace_root=config.workspace_root,
            parent_session_id=parent_session_id,
        )
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

    def append(
        self,
        session_id: str,
        entry: dict,
        *,
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> None:
        """Enqueue one JSONL entry for background flush.

        ``workspace_root`` locates the session file; omit it only when the store
        was constructed with a ``data_dir`` default base (legacy/tests).
        """

        path = self._resolve_path(
            session_id, workspace_root=workspace_root, parent_session_id=parent_session_id
        )
        self._writer.enqueue(path, entry)

    def load(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> LoadResult:
        """Load session config and message chain from JSONL.

        Handles compact_boundary skip and parent_uuid backtracking.
        Raises SessionNotFoundError when the file does not exist.

        ``workspace_root`` locates the session file; omit it only when the store
        was constructed with a ``data_dir`` default base (legacy/tests).
        """

        path = self._resolve_path(
            session_id, workspace_root=workspace_root, parent_session_id=parent_session_id
        )
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

    def update_config(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
        **fields: Any,
    ) -> None:
        """Append a config_update line.

        ``workspace_root`` locates the session file; omit it only when the store
        was constructed with a ``data_dir`` default base (legacy/tests).
        """

        path = self._resolve_path(session_id, workspace_root=workspace_root)
        entry: dict[str, Any] = {
            "type": "config_update",
            "session_id": session_id,
            "timestamp": _utc_now_iso(),
        }
        for key in ("system_prompt", "skills", "tool_allowlist", "metadata"):
            if key in fields and fields[key] is not None:
                entry[key] = fields[key]
        self._writer.enqueue(path, entry)

    def list_session_ids(
        self,
        *,
        limit: int,
        offset: int,
        workspace_root: Path | None = None,
    ) -> tuple[str, ...]:
        """List session ids by most recent mtime (main + subagent).

        Scoped to a single ``workspace_root`` (or ``data_dir`` when omitted and a
        default base was configured).  The stateless kernel has no global session
        registry, so there is no cross-workspace listing — callers list within the
        workspace they already know.
        """
        base = self._resolve_base(workspace_root)
        main_files = base.glob("sessions/*.jsonl")
        subagent_files = base.glob("sessions/*/subagents/*.jsonl")
        all_files = sorted(
            (*main_files, *subagent_files),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return tuple(p.stem for p in all_files[offset : offset + limit])

    @property
    def writer(self) -> JsonlWriter:
        return self._writer

    def resolve_path(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> Path:
        return self._resolve_path(
            session_id, workspace_root=workspace_root, parent_session_id=parent_session_id
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_base(self, workspace_root: Path | None) -> Path:
        """Resolve the ``.nano`` base directory for a session.

        Resolution:
        - ``data_dir`` was provided at construction → use it (test scaffolding
          only; the legacy flat layout). It wins so existing ``data_dir``-based
          tests keep all sessions under one tmp dir regardless of per-session
          ``workspace_root``.
        - else, ``workspace_root`` passed by the caller → ``{workspace_root}/.nano``
          (the production path; bootstrap always builds the store with
          ``data_dir=None``).
        - else → raise ``SessionNotFoundError``.  The stateless store never
          guesses a location: a missing ``workspace_root`` in production is a
          caller bug and must fail loudly, not silently fall back to a cwd-like
          default (which is exactly the bug bugfix-348 fixes).
        """
        if self._data_dir is not None:
            return self._data_dir
        if workspace_root is not None:
            return Path(workspace_root) / ".nano"
        raise SessionNotFoundError(
            "cannot resolve session path: the store was constructed with "
            "data_dir=None (production workspace-aware mode) but the caller did "
            "not pass workspace_root — refusing to guess the session location"
        )

    def _resolve_path(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
        parent_session_id: str | None = None,
    ) -> Path:
        base = self._resolve_base(workspace_root)
        if parent_session_id:
            return base / "sessions" / parent_session_id / "subagents" / f"{session_id}.jsonl"
        return base / "sessions" / f"{session_id}.jsonl"

    def find_session_by_metadata(
        self,
        *,
        parent_session_id: str | None,
        match: Mapping[str, Any],
        workspace_root: Path | None = None,
    ) -> str | None:
        """Return session_id whose metadata matches all key/value pairs in ``match``.

        Used by the ``agent`` tool to resolve ``agent_id`` -> subagent session_id
        when the in-memory registry entry has been lost (kernel restart, parent
        agent resume).  Scoped to one ``workspace_root`` — subagent JSONL lives
        under the parent session's workspace, which the running parent agent
        knows.  The agent index is rebuilt per call so it always reflects the
        passed workspace; it is not cached across differing workspace_roots.
        """
        agent_id = match.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            return None

        index = self._build_agent_index(workspace_root)

        results = index.get(agent_id)
        if not results:
            return None

        for found_session_id, found_parent in results:
            if parent_session_id is not None and found_parent != parent_session_id:
                continue
            return found_session_id
        return None

    def _build_agent_index(
        self, workspace_root: Path | None
    ) -> dict[str, list[tuple[str, str | None]]]:
        """Scan one workspace's session files and build the agent_id index."""
        index: dict[str, list[tuple[str, str | None]]] = {}
        sessions_dir = self._resolve_base(workspace_root) / "sessions"
        for path in sessions_dir.glob("*.jsonl"):
            session_id = path.stem
            parent_id = self._infer_parent_from_path(path)
            agent_id = self._read_agent_id_from_file(path)
            if agent_id:
                index.setdefault(agent_id, []).append((session_id, parent_id))
        for path in sessions_dir.glob("*/subagents/*.jsonl"):
            session_id = path.stem
            parent_id = self._infer_parent_from_path(path)
            agent_id = self._read_agent_id_from_file(path)
            if agent_id:
                index.setdefault(agent_id, []).append((session_id, parent_id))
        return index

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
