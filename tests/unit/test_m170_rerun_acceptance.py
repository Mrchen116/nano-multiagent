from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import importlib.util

import pytest


MODULE_PATH = Path("/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py")
SPEC = importlib.util.spec_from_file_location("m170_rerun_acceptance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
m170_rerun_acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m170_rerun_acceptance)


def _create_current_main_runtime_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                sender_user_id TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                content TEXT NOT NULL,
                attachments_json TEXT NOT NULL DEFAULT '[]',
                delivery_status TEXT NOT NULL DEFAULT 'sent',
                created_at TEXT NOT NULL
            );

            CREATE TABLE relay_tasks (
                relay_task_id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                target_node_id TEXT,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT,
                status TEXT NOT NULL,
                receipt_status TEXT,
                receipt_detail TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE conversation_events (
                event_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                message_id TEXT,
                event_type TEXT NOT NULL,
                delivery_status TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO messages (id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "msg-1",
                "conv-1",
                "user-1",
                "human",
                "@agent-m170-alpha please answer exactly as configured.",
                "[]",
                "delivered",
                "2026-03-16T10:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO relay_tasks (relay_task_id, message_id, conversation_id, target_node_id, payload_json, idempotency_key, status, receipt_status, receipt_detail, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "relay-1",
                "msg-1",
                "conv-1",
                "m170-node",
                json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 1}),
                "idem-1",
                "completed",
                "delivered",
                "ALPHA_ACK_M170",
                "2026-03-16T10:00:01Z",
                "2026-03-16T10:00:02Z",
            ),
        )
        connection.executemany(
            "INSERT INTO conversation_events (event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "evt-1",
                    "conv-1",
                    "msg-1",
                    "message.sent",
                    "sent",
                    json.dumps({"message_id": "msg-1"}),
                    "2026-03-16T10:00:00Z",
                ),
                (
                    "evt-2",
                    "conv-1",
                    "msg-1",
                    "relay.completed",
                    "delivered",
                    json.dumps({"relay_task_id": "relay-1", "receipt_detail": "ALPHA_ACK_M170"}),
                    "2026-03-16T10:00:02Z",
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def runtime_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "im_service.sqlite3"
    _create_current_main_runtime_db(db_path)
    monkeypatch.setattr(m170_rerun_acceptance, "DB_PATH", db_path)
    return db_path


def test_latest_message_matching_reads_current_main_message_schema(runtime_db: Path) -> None:
    row = m170_rerun_acceptance.latest_message_matching("@agent-m170-alpha please answer exactly as configured.")

    assert row == {
        "id": "msg-1",
        "conversation_id": "conv-1",
        "sender_user_id": "user-1",
        "sender_type": "human",
        "content": "@agent-m170-alpha please answer exactly as configured.",
        "created_at": "2026-03-16T10:00:00Z",
    }



def test_relay_for_message_reads_current_main_relay_schema(runtime_db: Path) -> None:
    row = m170_rerun_acceptance.relay_for_message("msg-1")

    assert row == {
        "relay_task_id": "relay-1",
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "target_node_id": "m170-node",
        "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 1}),
        "status": "completed",
        "receipt_status": "delivered",
        "receipt_detail": "ALPHA_ACK_M170",
    }



def test_events_for_message_reads_current_main_event_schema(runtime_db: Path) -> None:
    rows = m170_rerun_acceptance.events_for_message("msg-1")

    assert rows == [
        {
            "event_id": "evt-1",
            "event_type": "message.sent",
            "delivery_status": "sent",
            "payload_json": json.dumps({"message_id": "msg-1"}),
            "created_at": "2026-03-16T10:00:00Z",
        },
        {
            "event_id": "evt-2",
            "event_type": "relay.completed",
            "delivery_status": "delivered",
            "payload_json": json.dumps({"relay_task_id": "relay-1", "receipt_detail": "ALPHA_ACK_M170"}),
            "created_at": "2026-03-16T10:00:02Z",
        },
    ]



def test_no_reply_probe_flags_internal_status_leaks() -> None:
    body_text = "suppressed_by=no_reply_token\nAgent replied\nThe latest agent response finished successfully."

    probe = m170_rerun_acceptance.build_no_reply_probe(
        body_text=body_text,
        message={"id": "msg-2"},
        relay={"relay_task_id": "relay-2", "receipt_detail": "NO_REPLY"},
        events=[],
    )

    assert probe["status"] == "failed"
    assert probe["violations"] == [
        "NO_REPLY",
        "suppressed_by=no_reply_token",
        "Agent replied",
        "The latest agent response finished successfully.",
    ]



def test_result_json_includes_current_main_turn_summaries() -> None:
    result = m170_rerun_acceptance.build_turn_result(
        message={"id": "msg-1", "conversation_id": "conv-1"},
        relay={
            "relay_task_id": "relay-1",
            "receipt_detail": "ALPHA_ACK_M170",
            "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 3}),
        },
        events=[{"event_type": "message.sent"}, {"event_type": "relay.completed"}],
    )

    assert result == {
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "relay_task_id": "relay-1",
        "receipt_detail": "ALPHA_ACK_M170",
        "mentioned_agent_ids": ["agent-m170-alpha"],
        "config_profile_version": 3,
        "event_types": ["message.sent", "relay.completed"],
        "message": {"id": "msg-1", "conversation_id": "conv-1"},
        "relay": {
            "relay_task_id": "relay-1",
            "receipt_detail": "ALPHA_ACK_M170",
            "payload_json": json.dumps({"mentioned_agent_ids": ["agent-m170-alpha"], "config_profile_version": 3}),
        },
        "events": [{"event_type": "message.sent"}, {"event_type": "relay.completed"}],
    }
