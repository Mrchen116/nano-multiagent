"""Raw JSONL addressing and reads for conversation transcripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import SessionNotFoundError, SessionRef


class JsonlSessionFiles:
    """Resolve and read raw transcript files without owning session semantics."""

    def __init__(
        self,
        *,
        data_dir: Path | None,
        workspace_config_dirname: str = ".nano",
    ) -> None:
        if data_dir is not None:
            self._data_dir = Path(data_dir).expanduser().resolve()
            self._data_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._data_dir = None
        if not workspace_config_dirname:
            raise ValueError("workspace_config_dirname must be a non-empty string")
        self._workspace_config_dirname = workspace_config_dirname

    def resolve_path(self, ref: SessionRef) -> Path:
        """Resolve the JSONL path bound to ``ref`` without probing alternatives."""

        base = self._resolve_base(ref.workspace_root)
        if ref.parent_session_id:
            return (
                base
                / "sessions"
                / ref.parent_session_id
                / "subagents"
                / f"{ref.session_id}.jsonl"
            )
        return base / "sessions" / f"{ref.session_id}.jsonl"

    def read_raw_entries(self, ref: SessionRef) -> tuple[dict[str, Any], ...]:
        """Read all valid JSON objects at ``ref`` in append order."""

        path = self.resolve_path(ref)
        if not path.exists():
            raise SessionNotFoundError(ref.session_id)
        entries: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, dict):
                    entries.append(raw)
        return tuple(entries)

    def enumerate_addresses(self, *, workspace_root: Path) -> tuple[SessionRef, ...]:
        """Enumerate root and nested transcript addresses by descending mtime."""

        root = workspace_root.expanduser().resolve()
        base = self._resolve_base(root)
        files = sorted(
            (
                *base.glob("sessions/*.jsonl"),
                *base.glob("sessions/*/subagents/*.jsonl"),
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return tuple(
            SessionRef(
                session_id=path.stem,
                workspace_root=root,
                parent_session_id=self._parent_from_path(path),
            )
            for path in files
        )

    def _resolve_base(self, workspace_root: Path) -> Path:
        if self._data_dir is not None:
            return self._data_dir
        return workspace_root / self._workspace_config_dirname

    @staticmethod
    def _parent_from_path(path: Path) -> str | None:
        parts = path.parts
        try:
            index = parts.index("subagents")
        except ValueError:
            return None
        return parts[index - 1] if index >= 2 else None
