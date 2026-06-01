"""In-memory BackgroundTaskStore with optional manifest JSONL."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Sequence

from agent.core.background_tasks.models import (
    BackgroundTaskRecord,
    BackgroundTaskStatus,
)


class InMemoryTaskStore:
    """Process-local task store backed by an in-memory dict.

    Optional manifest JSONL appending for debugging and replay.
    """

    def __init__(self, *, manifest_path: Path | None = None) -> None:
        self._records: dict[str, BackgroundTaskRecord] = {}
        self._manifest_path = manifest_path
        self._lock = threading.Lock()

    def insert(self, record: BackgroundTaskRecord) -> None:
        with self._lock:
            self._records[record.task_id] = record
        self._append_manifest(record)

    def update(self, record: BackgroundTaskRecord) -> None:
        with self._lock:
            self._records[record.task_id] = record
        self._append_manifest(record)

    def get(self, task_id: str) -> BackgroundTaskRecord | None:
        with self._lock:
            return self._records.get(task_id)

    def list_non_terminal(self) -> Sequence[BackgroundTaskRecord]:
        with self._lock:
            return [
                r for r in self._records.values() if r.status not in _TERMINAL_STATUSES
            ]

    def _append_manifest(self, record: BackgroundTaskRecord) -> None:
        if self._manifest_path is None:
            return
        try:
            self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with self._manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(_record_to_dict(record), ensure_ascii=False) + "\n")
        except Exception:
            pass


_TERMINAL_STATUSES = {
    BackgroundTaskStatus.COMPLETED,
    BackgroundTaskStatus.FAILED,
    BackgroundTaskStatus.KILLED,
}


def _record_to_dict(record: BackgroundTaskRecord) -> dict[str, Any]:
    return {
        "task_id": record.task_id,
        "task_type": record.task_type.value,
        "parent_session_id": record.parent_session_id,
        "status": record.status.value,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "description": record.description,
        "output_file": record.output_file,
        "result_text": record.result_text,
        "error": record.error,
        "exit_code": record.exit_code,
        "duration_ms": record.duration_ms,
        "tool_use_count": record.tool_use_count,
        "notified": record.notified,
    }
