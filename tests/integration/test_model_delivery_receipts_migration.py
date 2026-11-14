"""Offline correction must preserve unrelated recipient delivery evidence."""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_center_correction_preserves_native_receipts_and_is_idempotent(tmp_path):
    database = tmp_path / "center.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE schema_migrations(version TEXT PRIMARY KEY);
            CREATE TABLE users(id TEXT,username TEXT);
            CREATE TABLE agent_profiles(agent_id TEXT,work_mode TEXT);
            CREATE TABLE message_receipts(message_id TEXT,recipient_id TEXT,status INTEGER);
            INSERT INTO users VALUES('g','agent:global'),('s','agent:single'),('h','human');
            INSERT INTO agent_profiles VALUES('global','global'),('single','single_thread');
            INSERT INTO message_receipts VALUES('pending','g',1),('read','g',2),('native','s',1),('human','h',1);
        """)
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts/migrate_model_delivery_receipts.py"
    )

    def run(action, *extra):
        return json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(script),
                    action,
                    "--kind",
                    "center",
                    "--database",
                    str(database),
                    *extra,
                ]
            )
        )

    assert run("dry-run")["candidates"] == 1
    assert run("apply", "--writers-stopped")["changed"] == 1
    with sqlite3.connect(database) as db:
        assert dict(db.execute("SELECT message_id,status FROM message_receipts")) == {
            "pending": 0,
            "read": 2,
            "native": 1,
            "human": 1,
        }
        db.execute("UPDATE message_receipts SET status=1 WHERE message_id='pending'")
    assert run("apply", "--writers-stopped")["changed"] == 0
    assert run("verify")["completed"]
    with sqlite3.connect(database) as db:
        assert db.execute(
            "SELECT status FROM message_receipts WHERE message_id='pending'"
        ).fetchone() == (1,)
