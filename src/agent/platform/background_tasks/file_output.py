"""File-based output for bash background tasks."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal


BACKGROUND_BASH_MAX_OUTPUT_BYTES = 256 * 1024 * 1024  # 256 MiB


class BashFileOutput:
    """Append-only file output for background bash tasks.

    Paths are resolved under ``<workspace_root>/.nano/background-tasks/<parent_session_id>/<task_id>.output``.
    Writes are thread-safe and capped at 256 MiB.
    """

    def __init__(self, *, workspace_root: Path) -> None:
        self._workspace_root = Path(workspace_root)
        self._handles: dict[str, _OutputHandle] = {}
        self._lock = threading.Lock()

    def open(self, parent_session_id: str, task_id: str) -> Path:
        path = self._resolve_path(parent_session_id, task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write initial status header so Read doesn't see a missing file.
        with path.open("w", encoding="utf-8") as f:
            f.write(f"# Background task {task_id} — output will appear here\n")
        with self._lock:
            self._handles[task_id] = _OutputHandle(path=path, bytes_written=0)
        return path

    def append(
        self, task_id: str, text: str, *, stream: Literal["stdout", "stderr"]
    ) -> None:
        with self._lock:
            handle = self._handles.get(task_id)
        if handle is None:
            return
        prefix = "[stderr] " if stream == "stderr" else ""
        chunk = prefix + text
        chunk_bytes = chunk.encode("utf-8")
        with handle.lock:
            if (
                handle.bytes_written + len(chunk_bytes)
                > BACKGROUND_BASH_MAX_OUTPUT_BYTES
            ):
                if not handle.truncated:
                    handle.truncated = True
                    notice = "\n[output truncated: exceeded 256 MiB limit]\n"
                    with handle.path.open("a", encoding="utf-8") as f:
                        f.write(notice)
                return
            with handle.path.open("a", encoding="utf-8") as f:
                f.write(chunk)
            handle.bytes_written += len(chunk_bytes)

    def flush(self, task_id: str) -> None:
        # File is opened/closed per append; no persistent handle to flush.
        pass

    def _resolve_path(self, parent_session_id: str, task_id: str) -> Path:
        return (
            self._workspace_root
            / ".nano"
            / "background-tasks"
            / parent_session_id
            / f"{task_id}.output"
        )


class _OutputHandle:
    def __init__(self, *, path: Path, bytes_written: int = 0) -> None:
        self.path = path
        self.bytes_written = bytes_written
        self.lock = threading.Lock()
        self.truncated = False
