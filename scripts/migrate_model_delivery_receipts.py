#!/usr/bin/env python3
"""Correct pre-model-delivery receipts in a stopped center or node Inbox database."""

import argparse
import json
from pathlib import Path
import sqlite3

VERSION = "model-delivery-receipts-v1"
CENTER_ROWS = """status=1 AND recipient_id IN (
    SELECT u.id FROM users u JOIN agent_profiles a ON u.username='agent:'||a.agent_id
)"""
INBOX_ROWS = """status='sent' AND (agent_id,message_id) IN (
    SELECT agent_id,message_id FROM inbox WHERE consumed=0
)"""


def migrate(database, kind, action, writers_stopped=False):
    """Apply one transactional correction, preserving read and human receipts.

    Args:
        database: Exact existing SQLite database path.
        kind: Either center or inbox.
        action: dry-run, apply or verify.
        writers_stopped: Operator confirmation required before applying changes.
    Returns:
        Migration status and affected row count without message content.
    """
    if action == "apply" and not writers_stopped:
        raise ValueError("Stop all old center/node writers before applying migration")
    path = Path(database).resolve(strict=True)
    mode = "rw" if action == "apply" else "ro"
    with sqlite3.connect(path.as_uri() + "?mode=" + mode, uri=True) as db:
        marker = (
            ("schema_migrations", "version")
            if kind == "center"
            else ("metadata", "key")
        )
        db.execute("BEGIN IMMEDIATE" if action == "apply" else "BEGIN")
        complete = bool(
            db.execute(
                f"SELECT 1 FROM {marker[0]} WHERE {marker[1]}=?", (VERSION,)
            ).fetchone()
        )
        if complete:
            return {"kind": kind, "completed": True, "changed": 0}
        if action == "verify":
            raise ValueError("Migration has not been applied")
        table, rows = (
            ("message_receipts", CENTER_ROWS)
            if kind == "center"
            else ("relay_receipts", INBOX_ROWS)
        )
        count = db.execute(f"SELECT count(*) FROM {table} WHERE {rows}").fetchone()[0]
        if action == "dry-run":
            return {"kind": kind, "completed": False, "candidates": count}
        if kind == "center":
            db.execute(f"UPDATE message_receipts SET status=0 WHERE {CENTER_ROWS}")
            db.execute("INSERT INTO schema_migrations(version) VALUES(?)", (VERSION,))
        else:
            db.execute("""INSERT OR IGNORE INTO metadata(key,value)
                SELECT 'receipt-recovery:'||i.agent_id,CAST(max(i.seq) AS TEXT)
                FROM inbox i JOIN relay_receipts r
                  ON r.agent_id=i.agent_id AND r.message_id=i.message_id
                WHERE i.consumed=0 AND r.status='sent' GROUP BY i.agent_id""")
            db.execute(
                f"UPDATE relay_receipts SET status='accepted',confirmed=0 WHERE {INBOX_ROWS}"
            )
            db.execute("INSERT INTO metadata(key,value) VALUES(?,'1')", (VERSION,))
        return {"kind": kind, "completed": True, "changed": count}


def main():
    """Run the explicit offline migration against one selected database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["dry-run", "apply", "verify"])
    parser.add_argument("--kind", choices=["center", "inbox"], required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(migrate(args.database, args.kind, args.action, args.writers_stopped))
    )


if __name__ == "__main__":
    main()
