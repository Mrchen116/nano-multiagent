"""Filesystem ownership for Workflow scripts, journals, and snapshots."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Mapping


class WorkflowRunStore:
    def __init__(
        self,
        *,
        workspace_root: Path,
        config_dirname: str,
        parent_session_id: str,
        run_id: str,
        slug: str,
    ) -> None:
        self.root = (
            workspace_root.expanduser().resolve()
            / config_dirname
            / "sessions"
            / parent_session_id
            / "workflows"
        )
        self.scripts_dir = self.root / "scripts"
        self.run_dir = self.root / "runs" / run_id
        self.script_path = self.scripts_dir / f"{slug}-{run_id}.py"
        self.snapshot_path = self.run_dir / "run.json"
        self.journal_path = self.run_dir / "journal.jsonl"
        self._lock = threading.Lock()

    def initialize(self, *, source: str, snapshot: Mapping[str, Any]) -> None:
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.script_path.write_text(source, encoding="utf-8")
        self.write_snapshot(snapshot)

    def append(self, event: Mapping[str, Any]) -> None:
        encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def write_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        encoded = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
        with self._lock:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            temp = self.snapshot_path.with_suffix(".json.tmp")
            temp.write_text(encoded + "\n", encoding="utf-8")
            temp.replace(self.snapshot_path)


def slugify_workflow_name(name: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in name
    )
    slug = "-".join(part for part in normalized.split("-") if part)
    return slug or "workflow"
