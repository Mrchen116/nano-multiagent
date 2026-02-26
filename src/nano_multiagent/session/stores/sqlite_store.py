import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.session.serializers import (
    deserialize_entry,
    deserialize_snapshot,
    serialize_entry,
    serialize_snapshot,
)
from nano_multiagent.session.stores.base import LoadedSession, SessionStore


class SQLiteSessionStore(SessionStore):
    def __init__(self, *, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def append_event(self, session_id: str, entry: Any) -> None:
        if entry.session_id != session_id:
            raise ValueError("entry.session_id must match append session_id")
        payload = json.dumps(serialize_entry(entry), separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_events(session_id, entry_id, created_at, payload)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, entry.entry_id, entry.created_at, payload),
            )

    def load_session(self, session_id: str) -> LoadedSession | None:
        with self._connect() as conn:
            event_rows = conn.execute(
                """
                SELECT payload
                FROM session_events
                WHERE session_id = ?
                ORDER BY seq ASC
                """,
                (session_id,),
            ).fetchall()
            snapshot_row = conn.execute(
                """
                SELECT payload
                FROM session_snapshots
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if not event_rows and snapshot_row is None:
            return None

        events = tuple(
            deserialize_entry(json.loads(row["payload"]))
            for row in event_rows
        )
        snapshot: Mapping[str, Any] | None = None
        if snapshot_row is not None:
            snapshot = deserialize_snapshot(json.loads(snapshot_row["payload"]))
        return LoadedSession(session_id=session_id, events=events, snapshot=snapshot)

    def save_snapshot(self, session_id: str, snapshot: Mapping[str, Any]) -> None:
        payload = json.dumps(serialize_snapshot(snapshot), separators=(",", ":"))
        updated_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_snapshots(session_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (session_id, payload, updated_at),
            )

    def list_session_ids(self, *, limit: int, offset: int) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id
                FROM session_events
                GROUP BY session_id
                ORDER BY MIN(seq) DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return tuple(str(row["session_id"]) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS session_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    entry_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_session_events_session_id_seq
                ON session_events(session_id, seq);

                CREATE TABLE IF NOT EXISTS session_snapshots (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
