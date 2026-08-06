"""SQLite-backed buffer for non-mention group chat messages.

Messages that arrive without an @mention are stored here so that when an
@mention later triggers execution the full conversation context is available.
Each message is stored with its sender identifier so the pipeline can
format ``[sender] text`` prefixes before handing context to the kernel.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS group_context_buffer (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    buf_key TEXT NOT NULL,
    text    TEXT NOT NULL,
    ts      REAL NOT NULL,
    sender  TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
)
"""

# Applied on _init_db to upgrade databases that predate M246 (no sender column).
_MIGRATION_ADD_SENDER = (
    "ALTER TABLE group_context_buffer ADD COLUMN sender TEXT NOT NULL DEFAULT ''"
)
_MIGRATION_ADD_METADATA = (
    "ALTER TABLE group_context_buffer "
    "ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
)


class GroupContextStore:
    """Persist and drain buffered group-chat context messages.

    Args:
        db_path: Path to the SQLite database file.  Created on first use.

    Notes:
        The ``sender`` field (M246) stores the external_user_id of the message
        author so the inbound pipeline can produce ``[sender] text`` prefixes.
        Existing databases without the column are migrated automatically.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        buf_key: str,
        text: str,
        *,
        sender: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Insert one buffered message row for ``buf_key``.

        Args:
            buf_key: Partition key combining agent_id + channel + chat_id.
            text: Plain-text message content.
            sender: External user identifier of the message author.
                    Empty string when sender is unknown or irrelevant.
            metadata: Small model-input projection retained with buffered content.
        """

        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO group_context_buffer "
                    "(buf_key, text, ts, sender, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        buf_key,
                        text,
                        time.time(),
                        sender,
                        json.dumps(dict(metadata or {}), ensure_ascii=False),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def drain(self, buf_key: str) -> list[tuple[str, str]]:
        """Atomically read and delete all buffered messages for ``buf_key``.

        Returns:
            List of ``(sender, text)`` tuples in insertion order.
            Empty when no rows exist.

        Notes:
            The ``sender`` field allows callers to format ``[sender] text``
            context prefixes before handing messages to the kernel.
        """

        return [
            (sender, text)
            for sender, text, _metadata in self.drain_with_metadata(buf_key)
        ]

    def drain_with_metadata(
        self, buf_key: str
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Atomically drain buffered text and its model-input projection."""

        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    rows = conn.execute(
                        "SELECT sender, text, metadata_json "
                        "FROM group_context_buffer WHERE buf_key = ? ORDER BY id",
                        (buf_key,),
                    ).fetchall()
                    conn.execute(
                        "DELETE FROM group_context_buffer WHERE buf_key = ?",
                        (buf_key,),
                    )
                return [(row[0], row[1], _decode_metadata(row[2])) for row in rows]
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
            # Migration: add sender column to databases created before M246.
            cols = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(group_context_buffer)"
                ).fetchall()
            }
            if "sender" not in cols:
                conn.execute(_MIGRATION_ADD_SENDER)
                conn.commit()
            if "metadata_json" not in cols:
                conn.execute(_MIGRATION_ADD_METADATA)
                conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))


def _decode_metadata(raw: object) -> dict[str, Any]:
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
