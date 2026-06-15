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
        (
            message_id,
            conversation_id,
            "agent-row-1",
            "agent",
            "",
            "[]",
            delivery_status,
            created_at,
        ),
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


def test_scan_inherits_prior_relay_processing_payload_for_id_continuity(
    tmp_path: Path,
) -> None:
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
    # Insert the relay.processing event with a stale created_at so the watchdog's
    # last-event-time check sees it as idle (bugfix-383: new SQL uses MAX(event.created_at)).
    # Payload must carry the identity fields to test inheritance.
    connection.execute(
        "INSERT INTO conversation_events(message_id, conversation_id, event_type, delivery_status, payload_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "msg-stuck",
            "conv-1",
            "relay.processing",
            "running",
            json.dumps(
                {
                    "conversation_id": "conv-1",
                    "message_id": "msg-stuck",
                    "relay_task_id": "task-abc",
                    "agent_id": "agent-A",
                    "node_id": "node-1",
                    "run_id": "run-xyz",
                    "progress_state": "processing",
                    "semantic": "agent_run_processing",
                }
            ),
            stale_at,
        ),
    )
    connection.commit()

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


def test_scan_writes_detail_into_empty_message_content(tmp_path: Path) -> None:
    """bugfix-365: when watchdog reaps a stuck running message whose content is empty
    (agent never emitted any streamed token), the timeout `detail` must be written
    into `messages.content` so the failed bubble renders it as bubble text instead
    of leaving an empty bubble + a separate anonymous "Agent" ghost bubble.
    """
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-empty",
        conversation_id="conv-1",
        created_at=stale_at,
    )

    repo = EventRepository(connection, notify=lambda _ev: None)
    scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=300,
    )
    row = connection.execute(
        "SELECT content, delivery_status FROM messages WHERE id = ?",
        ("msg-empty",),
    ).fetchone()
    assert row["delivery_status"] == "failed"
    assert row["content"] == "relay idle for 300s with no new event"


def test_scan_appends_error_note_to_partial_streamed_content(tmp_path: Path) -> None:
    """bugfix-365: when the stuck running message already has partial streamed
    content (agent emitted some tokens before the relay stalled), watchdog must
    preserve the streamed text and append `[error] <detail>` after a blank line,
    so users can still see what the agent produced before the timeout.
    """
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-partial",
        conversation_id="conv-1",
        created_at=stale_at,
    )
    connection.execute(
        "UPDATE messages SET content = ? WHERE id = ?",
        ("half a sentence...", "msg-partial"),
    )
    connection.commit()

    repo = EventRepository(connection, notify=lambda _ev: None)
    scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=300,
    )
    row = connection.execute(
        "SELECT content FROM messages WHERE id = ?", ("msg-partial",)
    ).fetchone()
    assert "half a sentence..." in row["content"]
    assert "[error] relay idle for 300s with no new event" in row["content"]


def test_scan_recovers_agent_identity_when_relay_processing_missing(
    tmp_path: Path,
) -> None:
    """bugfix-365: when no prior `relay.processing` exists (gateway crashed before
    emitting it), watchdog must still recover `agent_id` and `sender_display_name`
    from the `messages.sender_user_id` -> `users.username = agent:<id>` chain.
    Without this, the synthetic `relay.failed` event payload was missing identity
    fields and the frontend fell back to "Agent" for the sender label.
    """
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-noproc",
        conversation_id="conv-1",
        created_at=stale_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=300,
    )
    relay_failed = [ev for ev in captured if ev.event_type == "relay.failed"]
    assert len(relay_failed) == 1
    payload = json.loads(relay_failed[0].payload_json)
    assert payload.get("agent_id") == "agent-A"
    assert payload.get("sender_display_name") == "Agent A"


# ── bugfix-383: 判活信号改为"最近 event 时间" ──────────────────────────────


def _insert_conversation_event(
    connection,
    *,
    message_id: str,
    conversation_id: str,
    event_type: str,
    created_at: str,
) -> None:
    """直接向 conversation_events 插入原始行，绕开 repository 做时间控制。"""
    connection.execute(
        "INSERT INTO conversation_events(message_id, conversation_id, event_type, delivery_status, payload_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, conversation_id, event_type, "running", "{}", created_at),
    )
    connection.commit()


def test_active_relay_not_killed(tmp_path: Path) -> None:
    """bugfix-383: message 10 分钟前创建，但最近 event 30 秒前刚推进 → 不应被杀。

    这是本 bug 的核心回归测试：旧代码按 created_at 判断，10min > 120s 会被杀；
    新代码按最近 event 时间判断，30s < 120s 不被杀。
    """
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    old_created_at = _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=10))
    recent_event_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=30))
    _insert_conversation_and_message(
        connection,
        message_id="msg-active",
        conversation_id="conv-1",
        created_at=old_created_at,
    )
    _insert_conversation_event(
        connection,
        message_id="msg-active",
        conversation_id="conv-1",
        event_type="tool_call.upserted",
        created_at=recent_event_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
    )

    assert flipped == 0
    row = connection.execute(
        "SELECT delivery_status FROM messages WHERE id = ?", ("msg-active",)
    ).fetchone()
    assert row["delivery_status"] == "running"
    assert captured == []


def test_idle_relay_killed_with_new_wording(tmp_path: Path) -> None:
    """bugfix-383: message 10 分钟前创建，最后 event 5 分钟前 → 应被杀，文案用新格式。"""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    old_created_at = _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=10))
    old_event_at = _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=5))
    _insert_conversation_and_message(
        connection,
        message_id="msg-idle",
        conversation_id="conv-1",
        created_at=old_created_at,
    )
    _insert_conversation_event(
        connection,
        message_id="msg-idle",
        conversation_id="conv-1",
        event_type="tool_call.upserted",
        created_at=old_event_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
    )

    assert flipped == 1
    row = connection.execute(
        "SELECT delivery_status, content FROM messages WHERE id = ?", ("msg-idle",)
    ).fetchone()
    assert row["delivery_status"] == "failed"
    assert "relay idle for 120s with no new event" in row["content"]


def test_no_event_fallback_to_created_at(tmp_path: Path) -> None:
    """bugfix-383: message 4 分钟前创建，零 conversation_events → fallback 到 created_at，被杀（> 120s）。"""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    created_at = _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=4))
    _insert_conversation_and_message(
        connection,
        message_id="msg-noevent",
        conversation_id="conv-1",
        created_at=created_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
    )

    assert flipped == 1
    row = connection.execute(
        "SELECT delivery_status FROM messages WHERE id = ?", ("msg-noevent",)
    ).fetchone()
    assert row["delivery_status"] == "failed"


def test_boundary_just_over_idle_threshold(tmp_path: Path) -> None:
    """last_evt 121s 前 → idle > 120s，应被杀。"""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    old_created_at = _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=10))
    last_event_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=121))
    _insert_conversation_and_message(
        connection,
        message_id="msg-over",
        conversation_id="conv-1",
        created_at=old_created_at,
    )
    _insert_conversation_event(
        connection,
        message_id="msg-over",
        conversation_id="conv-1",
        event_type="message.delta",
        created_at=last_event_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
    )

    assert flipped == 1


def test_boundary_just_under_idle_threshold(tmp_path: Path) -> None:
    """last_evt 119s 前 → idle < 120s，不应被杀。"""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    old_created_at = _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=10))
    last_event_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=119))
    _insert_conversation_and_message(
        connection,
        message_id="msg-under",
        conversation_id="conv-1",
        created_at=old_created_at,
    )
    _insert_conversation_event(
        connection,
        message_id="msg-under",
        conversation_id="conv-1",
        event_type="message.delta",
        created_at=last_event_at,
    )

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
    )

    assert flipped == 0


# ---------------------------------------------------------------------------
# bugfix-410-M2 R2 (#98): awaiting_permission marker exempts a running message
# from the 120s relay reap WHILE a permission decision is pending — but only as
# long as the marker is live (Gateway heartbeat keeps touching its timestamp).
# A Gateway crash stops the refresh; the marker then goes stale past a crash
# threshold (independent of 120s, several × heartbeat interval) and the message
# is reaped as usual, so a crash cannot leak a permanently-exempt ghost.
# ---------------------------------------------------------------------------


def _set_awaiting_permission_at(connection, *, message_id: str, at: str | None) -> None:
    connection.execute(
        "UPDATE messages SET awaiting_permission_at = ? WHERE id = ?",
        (at, message_id),
    )
    connection.commit()


def test_scan_skips_running_message_with_fresh_permission_marker(
    tmp_path: Path,
) -> None:
    """A running message stale by the 120s rule is NOT reaped while its
    awaiting_permission marker is fresh (user still deciding, Gateway alive)."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    # 600s old by created_at → would normally be reaped at timeout=120.
    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-awaiting",
        conversation_id="conv-1",
        created_at=stale_at,
    )
    # But the permission marker was refreshed 5s ago (Gateway heartbeat).
    fresh_marker = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=5))
    _set_awaiting_permission_at(connection, message_id="msg-awaiting", at=fresh_marker)

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
        permission_crash_threshold_seconds=300,
    )

    assert flipped == 0, "fresh permission marker must exempt the message from reap"
    row = connection.execute(
        "SELECT delivery_status FROM messages WHERE id = ?", ("msg-awaiting",)
    ).fetchone()
    assert row["delivery_status"] == "running"


def test_scan_reaps_running_message_with_stale_permission_marker(
    tmp_path: Path,
) -> None:
    """A Gateway crash stops marker refresh → marker goes stale past the crash
    threshold → the message is reaped as usual (no permanent ghost)."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)

    stale_at = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=600))
    _insert_conversation_and_message(
        connection,
        message_id="msg-crashed",
        conversation_id="conv-1",
        created_at=stale_at,
    )
    # Marker last touched 400s ago — Gateway crashed; exceeds 300s crash threshold.
    stale_marker = _utc_iso(datetime.now(timezone.utc) - timedelta(seconds=400))
    _set_awaiting_permission_at(connection, message_id="msg-crashed", at=stale_marker)

    captured: list[ConversationEvent] = []
    repo = EventRepository(connection, notify=captured.append)
    flipped = scan_and_fail_stuck_running_messages(
        connection=connection,
        event_repository=repo,
        timeout_seconds=120,
        permission_crash_threshold_seconds=300,
    )

    assert flipped == 1, "stale permission marker must NOT exempt — crash ghost reaped"
    row = connection.execute(
        "SELECT delivery_status FROM messages WHERE id = ?", ("msg-crashed",)
    ).fetchone()
    assert row["delivery_status"] == "failed"
