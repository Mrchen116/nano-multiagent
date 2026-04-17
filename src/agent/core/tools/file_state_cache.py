"""Per-session file read state cache for mtime-based deduplication."""

from pathlib import Path
from typing import Any


class FileStateCache:
    """Lightweight LRU cache storing file metadata (mtime, size) keyed by read range."""

    def __init__(self, capacity: int = 128) -> None:
        self._capacity = max(1, capacity)
        self._data: dict[tuple[Path, int | None, int | None], tuple[int, int]] = {}
        self._order: list[tuple[Path, int | None, int | None]] = []

    def get(self, key: tuple[Path, int | None, int | None]) -> tuple[int, int] | None:
        if key not in self._data:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._data[key]

    def set(self, key: tuple[Path, int | None, int | None], value: tuple[int, int]) -> None:
        if key in self._data:
            self._order.remove(key)
        self._order.append(key)
        self._data[key] = value
        if len(self._order) > self._capacity:
            evicted = self._order.pop(0)
            self._data.pop(evicted, None)


class SessionFileReadCache:
    """Manage session-isolated FileStateCache instances."""

    def __init__(self, capacity: int = 128) -> None:
        self._capacity = capacity
        self._sessions: dict[str, FileStateCache] = {}

    def get(self, session_id: str) -> FileStateCache:
        if session_id not in self._sessions:
            self._sessions[session_id] = FileStateCache(capacity=self._capacity)
        return self._sessions[session_id]

    def drop(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
