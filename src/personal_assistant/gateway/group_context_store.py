"""SQLite-backed buffer for non-mention group chat messages.

Messages that arrive without an @mention are stored here so that when an
@mention later triggers execution the full conversation context is available.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS group_context_buffer (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    buf_key TEXT NOT NULL,
    text    TEXT NOT NULL,
    ts      REAL NOT NULL
)
"""


class GroupContextStore:
    """Persist and drain buffered group-chat context messages.

    Args:
        db_path: Path to the SQLite database file.  Created on first use.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, buf_key: str, text: str) -> None:
        """Insert one buffered message row for ``buf_key``."""

        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO group_context_buffer (buf_key, text, ts) VALUES (?, ?, ?)",
                    (buf_key, text, time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    def drain(self, buf_key: str) -> list[str]:
        """Atomically read and delete all buffered messages for ``buf_key``.

        Returns:
            List of message texts in insertion order.  Empty when no rows exist.
        """

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    rows = conn.execute(
                        "SELECT text FROM group_context_buffer WHERE buf_key = ? ORDER BY id",
                        (buf_key,),
                    ).fetchall()
                    conn.execute(
                        "DELETE FROM group_context_buffer WHERE buf_key = ?",
                        (buf_key,),
                    )
                return [row[0] for row in rows]
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))
