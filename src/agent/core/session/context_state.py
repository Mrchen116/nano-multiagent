"""Conversation-owned memory and file-window state."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class MemorySnapshot(TypedDict):
    """Store the compaction-window-stable memory projection for one session."""

    memory_content: str | None
    memory_pct: int
    user_profile_content: str | None
    user_pct: int
    agents_md_content: str | None


@dataclass(frozen=True, slots=True)
class FileReadState:
    """Snapshot a file fingerprint and its last read range."""

    file_path: str
    mtime_ns: int
    size: int
    offset: int | None
    limit: int | None


class SessionFileState:
    """Track read de-duplication and read-before-write state for one session."""

    def __init__(self, capacity: int = 128) -> None:
        self._capacity = max(1, capacity)
        self._states: OrderedDict[str, FileReadState] = OrderedDict()
        self.loaded_agents_md: set[str] = set()

    def check_unchanged(
        self, file_path: str, offset: int | None, limit: int | None
    ) -> bool:
        """Return whether the same range remains byte-for-byte unchanged."""

        normalized = str(Path(file_path).resolve())
        state = self._states.get(normalized)
        if state is None or state.offset != offset or state.limit != limit:
            return False
        try:
            stat = Path(file_path).stat()
        except (OSError, ValueError):
            return False
        return stat.st_mtime_ns == state.mtime_ns and stat.st_size == state.size

    def record_read(
        self,
        file_path: str,
        mtime_ns: int,
        size: int,
        offset: int | None,
        limit: int | None,
    ) -> None:
        """Record the latest successful read and evict the oldest fingerprint."""

        self._record(
            FileReadState(
                file_path=str(Path(file_path).resolve()),
                mtime_ns=mtime_ns,
                size=size,
                offset=offset,
                limit=limit,
            )
        )

    def can_write(self, file_path: str) -> tuple[bool, int | None]:
        """Return whether a file was read and has not changed since that read."""

        normalized = str(Path(file_path).resolve())
        state = self._states.get(normalized)
        if state is None:
            return False, 6
        try:
            stat = Path(file_path).stat()
        except (OSError, ValueError):
            return False, 6
        if stat.st_mtime_ns != state.mtime_ns or stat.st_size != state.size:
            return False, 7
        return True, None

    def record_write(self, file_path: str, mtime_ns: int, size: int) -> None:
        """Refresh a fingerprint after this session successfully writes a file."""

        self._record(
            FileReadState(
                file_path=str(Path(file_path).resolve()),
                mtime_ns=mtime_ns,
                size=size,
                offset=None,
                limit=None,
            )
        )

    def remove(self, file_path: str) -> None:
        """Forget the fingerprint for a deleted file."""

        self._states.pop(str(Path(file_path).resolve()), None)

    def _record(self, state: FileReadState) -> None:
        if state.file_path in self._states:
            self._states.move_to_end(state.file_path)
        self._states[state.file_path] = state
        if len(self._states) > self._capacity:
            self._states.popitem(last=False)


def read_file_slice(
    file_path: str,
    offset: int | None,
    limit: int | None,
) -> str | None:
    """Read a whole file or a one-indexed line slice, returning None on failure."""

    try:
        path = Path(file_path)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        if offset is None or limit is None:
            return text
        lines = text.splitlines()
        start = max(0, offset - 1)
        return "\n".join(lines[start : start + limit])
    except (OSError, ValueError):
        return None
