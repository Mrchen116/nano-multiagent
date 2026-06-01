"""Session-scoped file read state tracker.

Replaces FileStateCache with a unified container that supports both
Read deduplication and Read-Before-Write enforcement.
"""

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileReadState:
    """Snapshot of a file at the time it was last read or written."""

    file_path: str  # normalized absolute path
    mtime_ns: int
    size: int
    offset: int | None  # last read offset (1-indexed); None = from start
    limit: int | None  # last read limit; None = to end


class SessionFileState:
    """Session-scoped file read state tracker.

    Dual-purpose:
    1. Read dedup: file_unchanged when exact range matches and mtime/size are identical.
    2. Read-Before-Write: can_write() enforces that a file has been read and is not stale.

    NOTE: Each file retains only its *last* read range. If the model alternates
    between reading different ranges of the same file (e.g. offset 1-50 then
    51-100 then back to 1-50), the earlier range dedup info is lost and the
    third read will hit disk. This is an acceptable tradeoff for a single
    container design, but review carefully if changing dedup granularity.
    """

    def __init__(self, capacity: int = 128) -> None:
        self._capacity = max(1, capacity)
        self._states: OrderedDict[str, FileReadState] = OrderedDict()

    def check_unchanged(
        self, file_path: str, offset: int | None, limit: int | None
    ) -> bool:
        """Return True if this exact range was last read and file is unchanged."""
        normalized = str(Path(file_path).resolve())
        state = self._states.get(normalized)
        if state is None:
            return False
        if state.offset != offset or state.limit != limit:
            return False
        try:
            stat = Path(file_path).stat()
            return stat.st_mtime_ns == state.mtime_ns and stat.st_size == state.size
        except (OSError, ValueError):
            return False

    def record_read(
        self,
        file_path: str,
        mtime_ns: int,
        size: int,
        offset: int | None,
        limit: int | None,
    ) -> None:
        """Record a successful read, overwriting the last range for this file."""
        normalized = str(Path(file_path).resolve())
        state = FileReadState(
            file_path=normalized,
            mtime_ns=mtime_ns,
            size=size,
            offset=offset,
            limit=limit,
        )
        if normalized in self._states:
            self._states.move_to_end(normalized)
        self._states[normalized] = state
        if len(self._states) > self._capacity:
            self._states.popitem(last=False)

    def can_write(self, file_path: str) -> tuple[bool, int | None]:
        """Check whether the file may be overwritten/edited.

        Returns:
            (True, None)  -- allowed (read and not stale)
            (False, 6)    -- errorCode 6: file has not been read
            (False, 7)    -- errorCode 7: file is stale
        """
        normalized = str(Path(file_path).resolve())
        state = self._states.get(normalized)
        if state is None:
            return False, 6
        try:
            stat = Path(file_path).stat()
            if stat.st_mtime_ns != state.mtime_ns or stat.st_size != state.size:
                return False, 7
            return True, None
        except (OSError, ValueError):
            return False, 6

    def record_write(self, file_path: str, mtime_ns: int, size: int) -> None:
        """Record a successful write, updating fingerprint to prevent self-edit stale false positives.

        After a write the offset/limit become None/None because the entire
        file was rewritten.
        """
        normalized = str(Path(file_path).resolve())
        state = FileReadState(
            file_path=normalized,
            mtime_ns=mtime_ns,
            size=size,
            offset=None,
            limit=None,
        )
        if normalized in self._states:
            self._states.move_to_end(normalized)
        self._states[normalized] = state
        if len(self._states) > self._capacity:
            self._states.popitem(last=False)

    def remove(self, file_path: str) -> None:
        """Drop state for a deleted file."""
        normalized = str(Path(file_path).resolve())
        self._states.pop(normalized, None)


def read_file_slice(
    file_path: str,
    offset: int | None,
    limit: int | None,
) -> str | None:
    """Read a file or a slice of it (offset/limit are 1-indexed line numbers).

    Previously defined in runtime.py; migrated here to break the
    loop -> runtime import cycle.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        if offset is None or limit is None:
            return text
        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        return "\n".join(lines[start:end])
    except (OSError, ValueError):
        return None
