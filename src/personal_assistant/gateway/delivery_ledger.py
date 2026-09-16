"""Durable Gateway publication identities and channel receipts."""

from pathlib import Path
from threading import RLock
from typing import Any
import hashlib
import json
import sqlite3
import time


class DeliveryLedger:
    """Own message receipts independently of immutable image resources."""

    def __init__(self, root: Path):
        self._db = root / "reply_images.sqlite3"
        self._lock = RLock()
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS delivery_feedback (request_id TEXT, submission_id TEXT, PRIMARY KEY(request_id, submission_id))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reply_deliveries (output_key TEXT, channel TEXT, receipt_json TEXT NOT NULL, PRIMARY KEY(output_key, channel))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reply_dispatch_inputs (input_key TEXT PRIMARY KEY, call_id TEXT NOT NULL, output_key TEXT NOT NULL)"
            )

    def delivery_receipt(self, output_key: str, channel: str) -> dict[str, Any] | None:
        """Load durable delivery state for one stable output and destination."""
        with self._lock, sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT receipt_json FROM reply_deliveries WHERE output_key=? AND channel=?",
                (output_key, channel),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def dispatch_identity(
        self, *, agent_id: str, session_id: str, target: str, text: str, call_id: str
    ) -> str:
        """Reuse an unresolved send identity while allowing later intentional sends."""
        input_key = hashlib.sha256(
            json.dumps(
                [agent_id, session_id, target, text], ensure_ascii=False
            ).encode()
        ).hexdigest()
        with self._lock, sqlite3.connect(self._db) as conn:
            previous = conn.execute(
                "SELECT call_id, output_key FROM reply_dispatch_inputs WHERE input_key=?",
                (input_key,),
            ).fetchone()
            if previous:
                receipts = [
                    json.loads(row[0])
                    for row in conn.execute(
                        "SELECT receipt_json FROM reply_deliveries WHERE output_key=?",
                        (previous[1],),
                    ).fetchall()
                ]
                if receipts and any(
                    item.get("state", item.get("status")) != "delivered"
                    for item in receipts
                ):
                    return previous[0]
            output_key = f"dispatch:{agent_id}:{session_id}:{call_id}"
            conn.execute(
                "INSERT OR REPLACE INTO reply_dispatch_inputs VALUES (?,?,?)",
                (input_key, call_id, output_key),
            )
            return call_id

    def unresolved_deliveries(
        self, *, limit: int = 100
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """List bounded unresolved channel publications that have replay payloads."""
        with self._lock, sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT output_key, channel, receipt_json FROM reply_deliveries "
                "WHERE json_extract(receipt_json, '$.recovery') IS NOT NULL "
                "AND COALESCE(json_extract(receipt_json, '$.state'), json_extract(receipt_json, '$.status'), '') != 'delivered' "
                "ORDER BY rowid LIMIT ?",
                (limit,),
            ).fetchall()
        return [(key, channel, json.loads(receipt)) for key, channel, receipt in rows]

    def record_delivery(
        self, output_key: str, channel: str, receipt: dict[str, Any]
    ) -> None:
        """Persist confirmed or uncertain delivery before another attempt."""
        with self._lock, sqlite3.connect(self._db) as conn:
            previous = conn.execute(
                "SELECT receipt_json FROM reply_deliveries WHERE output_key=? AND channel=?",
                (output_key, channel),
            ).fetchone()
            prior = json.loads(previous[0]) if previous else {}
            receipt = dict(receipt)
            if "first_attempt_at" in prior:
                receipt["first_attempt_at"] = prior["first_attempt_at"]
            elif receipt.get("recovery", {}).get("kind") == "external_prepared":
                receipt.setdefault("first_attempt_at", time.time())
            conn.execute(
                "INSERT OR REPLACE INTO reply_deliveries VALUES (?,?,?)",
                (output_key, channel, json.dumps(receipt)),
            )

    def next_submission(self, logical_request_id):
        with self._lock, sqlite3.connect(self._db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM delivery_feedback WHERE request_id=?",
                (logical_request_id,),
            ).fetchone()[0]
        if count >= 2:
            return None
        ordinal = count + 1
        return f"delivery-feedback:{logical_request_id}:{ordinal}", ordinal

    def record_admitted(self, logical_request_id, submission_id):
        with self._lock, sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO delivery_feedback VALUES (?, ?)",
                (logical_request_id, submission_id),
            )
