"""Unit tests for the IM relay watchdog (bugfix-361 / issue #22)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from IM.application.relay_watchdog import scan_and_fail_stuck_running_messages
from IM.domain.models import ConversationEvent
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import EventRepository


def _utc_iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _insert_conversation_and_message(
    connection,
    *,
    message_id: str,
    conversation_id: str,
    created_at: str,
    delivery_status: str = "running",
) -> None:
    """Lowest-level fixture: bypass repository validations to seed a stuck row directly."""
    connection.execute(
        "INSERT INTO users(id, username, display_name, owner_id, password_hash, locale, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("owner-1", "owner", "Owner", "owner-1", "x", "en", created_at),
    )
    connection.execute(
        "INSERT OR IGNORE INTO users(id, username, display_name, owner_id, password_hash, locale, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("agent-row-1", "agent:agent-A", "Agent A", "owner-1", "x", "en", created_at),
    )
    connection.execute(
        "INSERT INTO conversations(id, owner_id, title, type, created_at) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, "owner-1", "t", "direct", created_at),
    )
    connection.execute(
        "INSERT INTO messages(id, conversation_id, sender_user_id, sender_type, content, attachments_json, "
        "delivery_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (message_id, conversation_id, "agent-row-1", "agent", "", "[]", delivery_status, created_at),
    )
    connection.commit()


def test_scan_flips_stale_running_message_to_failed(tmp_path: Path) -> None:
    """A `running` message older than the cutoff gets flipped to `failed` and a `relay.failed` event fires."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-stuck",
        conversation_id="conv-1",
        created_at=stale_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)

    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=300,
    )

    assert flipped == 1
    row = connection.execute(
        "SELECT delivery_status FROM messages WHERE id = ?", ("msg-stuck",)
    ).fetchone()
    assert row["delivery_status"] == "failed"

    relay_failed = [ev for ev in captured if ev.event_type == "relay.failed"]
    assert len(relay_failed) == 1
    payload = json.loads(relay_failed[0].payload_json)
    assert payload["message_id"] == "msg-stuck"
    assert payload["conversation_id"] == "conv-1"
    assert payload["semantic"] == "relay_watchdog_timeout"
    assert payload["progress_state"] == "failed"


def test_scan_skips_fresh_running_message(tmp_path: Path) -> None:
    """A `running` message within the timeout window is left alone."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    fresh_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=60))
    _insert_conversation_and_message(
        connection,
        message_id="msg-fresh",
        conversation_id="conv-1",
        created_at=fresh_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)

    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=300,
    )

    assert flipped == 0
    row = connection.execute(
        "SELECT delivery_status FROM messages WHERE id = ?", ("msg-fresh",)
    ).fetchone()
    assert row["delivery_status"] == "running"
    assert captured == []


def test_scan_skips_already_terminal_messages(tmp_path: Path) -> None:
    """Messages already in `completed`/`failed` are never touched, regardless of age."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-done",
        conversation_id="conv-1",
        created_at=stale_at,
        delivery_status="completed",
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)

    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=300,
    )

    assert flipped == 0
    assert captured == []


def test_scan_inherits_prior_relay_processing_payload_for_id_continuity(tmp_path: Path) -> None:
    """The synthetic `relay.failed` payload mirrors the prior `relay.processing` so the frontend's
    synthetic-message id stays stable and the bubble flips in place rather than duplicating."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-stuck",
        conversation_id="conv-1",
        created_at=stale_at,
    )
    repo = EventRepository(connection, notify=lambda _ev: None)
    # Seed the original relay.processing event the way GatewayHandler does.
    repo.append_event(
        conversation_id="conv-1",
        message_id="msg-stuck",
        event_type="relay.processing",
        delivery_status="running",
        payload={
            "conversation_id": "conv-1",
            "message_id": "msg-stuck",
            "relay_task_id": "task-abc",
            "agent_id": "agent-A",
            "node_id": "node-1",
            "run_id": "run-xyz",
            "progress_state": "processing",
            "semantic": "agent_run_processing",
        },
    )

    captured: list[ConversationEvent] = []
    repo_recorded = EventRepository(connection, notify=captured.append)

    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo_recorded,
        timeout_seconds=300,
    )
    assert flipped == 1
    relay_failed = [ev for ev in captured if ev.event_type == "relay.failed"]
    assert len(relay_failed) == 1
    payload = json.loads(relay_failed[0].payload_json)
    assert payload["relay_task_id"] == "task-abc"
    assert payload["agent_id"] == "agent-A"
    assert payload["node_id"] == "node-1"
    assert payload["run_id"] == "run-xyz"
