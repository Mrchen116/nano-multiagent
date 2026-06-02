"""Atomic file-write utility shared across agent.core.

Two modules (memory.store, skills.writer) each carried a private _atomic_write
copy — consolidated here as refactor-395-M1.

The write is atomic on POSIX: a temp file is created in the same directory
(guaranteeing same-filesystem rename) then os.replace'd into place. fsync
ensures durability before the rename.
"""

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: str | bytes, *, encoding: str = "utf-8") -> None:
    """Write *data* to *path* atomically via temp file + os.replace.

    Args:
        path: Destination file path. Parent directory must already exist.
        data: Content to write. str is encoded with *encoding*; bytes written
            as-is.
        encoding: Text encoding used when *data* is a str. Ignored for bytes.

    Raises:
        OSError: If the write or rename fails (temp file cleaned up first).
    """
    raw: bytes = data.encode(encoding) if isinstance(data, str) else data
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.tmp.",
        suffix="",
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
