"""Watchdog that finalises orphan `running` messages whose Gateway-side relay never terminates.

Without this, any Gateway crash / network drop / LLM hang mid-stream leaves the IM
placeholder message permanently in `delivery_status='running'`, and the UI keeps showing
"agent is replying" forever (see bugfix-361 / issue #22). The Gateway is not a trustworthy
oracle for terminal state; IM must guarantee its own state can be reaped.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from IM.infra.repositories import EventRepository, _format_utc

logger = logging.getLogger(__name__)


def scan_and_fail_stuck_running_messages(
    *,
    connection: sqlite3.Connection,
    event_repository: EventRepository,
    timeout_seconds: int = 120,
) -> int:
    """Find messages idle in `running` past the cutoff, fail them, and push `relay.failed`.

    Args:
        connection: SQLite connection used to scan `messages` / `conversation_events`.
        event_repository: Used to append the synthetic `relay.failed` event so WS clients
            see the placeholder flip without an extra round trip.
        timeout_seconds: Idle window — seconds since the last `conversation_events` row for
            this message (or `messages.created_at` when no events exist) past which a
            `running` message is considered stuck. Default 2 minutes: active tool-loop
            relays push events every few seconds, so 120s of silence means truly stuck.

    Returns:
        Number of messages flipped from `running` to `failed` in this pass.
    """
    # bugfix-410-fix-r1: format the cutoff via repositories._format_utc so the SQL string
    # comparison below can never break from a format drift between writer and comparator.
    now = datetime.now(timezone.utc)
    cutoff = _format_utc(now - timedelta(seconds=timeout_seconds))
    # bugfix-383: judge liveness by the most recent event timestamp, not message
    # creation time. Multi-turn tool loops run for many minutes while pushing events
    # continuously; only silence (no new event) for `timeout_seconds` means stuck.
    # COALESCE falls back to created_at when no events exist (gateway crashed before
    # emitting relay.processing) — preserves the original behaviour for that edge case.
    #
    # bugfix-417-M3 R4: the permission-specific awaiting_permission_at exemption is gone.
    # All three alive-but-quiet windows (silent long tool / awaiting LLM / parked on a
    # permission decision) now emit a uniform run_heartbeat that EventBridge persists as a
    # conversation_events row — so last_evt advances for every live window and the single
    # liveness judgment below covers them with no per-window special case. A Gateway/kernel
    # crash stops the heartbeat → last_evt goes stale → the row is reaped normally
    # (decision 4 crash detection), strictly faster than the old 600s marker threshold.
    rows = connection.execute(
        """
        SELECT m.id, m.conversation_id, m.created_at
        FROM messages m
        LEFT JOIN (
            SELECT message_id, MAX(created_at) AS last_evt
            FROM conversation_events
            GROUP BY message_id
        ) e ON e.message_id = m.id
        WHERE m.delivery_status = 'running'
          AND COALESCE(e.last_evt, m.created_at) < ?
        """,
        (cutoff,),
    ).fetchall()
    if not rows:
        return 0

    flipped = 0
    detail_text = f"relay idle for {timeout_seconds}s with no new event"
    for row in rows:
        message_id = str(row["id"])
        conversation_id = str(row["conversation_id"])
        payload = _build_failed_payload(
            connection=connection,
            conversation_id=conversation_id,
            message_id=message_id,
            timeout_seconds=timeout_seconds,
        )
        try:
            event_repository.append_event(
                conversation_id=conversation_id,
                message_id=message_id,
                event_type="relay.failed",
                delivery_status="failed",
                payload=payload,
            )
            event_repository.update_message_delivery_status(
                message_id=message_id,
                delivery_status="failed",
            )
            # bugfix-365: backfill the failure detail into the real message row so
            # the failed bubble carries readable text. Without this, the bubble is
            # blank (agent never streamed any token before the stall) and we had
            # to render a separate synthetic "Agent" bubble — which then duplicated
            # the row in the UI. Append after partial content to preserve any text
            # the agent did manage to stream before the relay died.
            _backfill_failure_detail_into_message_content(
                connection=connection,
                message_id=message_id,
                detail_text=detail_text,
            )
        except Exception:  # noqa: BLE001 — one bad row should not poison the whole sweep
            logger.exception("relay_watchdog: failed to reap message %s", message_id)
            continue
        flipped += 1
        logger.warning(
            "relay_watchdog: reaped stuck message %s in conversation %s (age > %ds)",
            message_id,
            conversation_id,
            timeout_seconds,
        )
    return flipped


def _build_failed_payload(
    *,
    connection: sqlite3.Connection,
    conversation_id: str,
    message_id: str,
    timeout_seconds: int,
) -> dict[str, object]:
    """Mirror the original `relay.processing` payload so the frontend's synthetic-message
    mapper produces the same row id and just flips status instead of duplicating the bubble.
    """
    base: dict[str, object] = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "progress_state": "failed",
        # `semantic` identifies WHICH path produced the failure (the IM relay DB-sweep
        # fallback) and stays relay-specific. `reason` is the failure-cause vocabulary
        # shared with the Gateway watchdog: both reap a message/run that lost liveness
        # within the idle window, so both use "stalled" (bugfix-417-M4: aligned from the
        # former "watchdog_timeout" to remove the watchdog_timeout≠stalled inconsistency
        # the two watchdogs carried for the same semantic).
        "semantic": "relay_watchdog_timeout",
        "detail": f"relay idle for {timeout_seconds}s with no new event",
        "reason": "stalled",
    }
    row = connection.execute(
        """
        SELECT payload_json
        FROM conversation_events
        WHERE message_id = ? AND event_type = 'relay.processing'
        ORDER BY event_id DESC
        LIMIT 1
        """,
        (message_id,),
    ).fetchone()
    if row is not None:
        try:
            prior = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            prior = None
        if isinstance(prior, dict):
            # Inherit relay_task_id / agent_id / node_id / run_id / display_name so the
            # frontend can attribute the failure to the same agent identity.
            for key in (
                "relay_task_id",
                "agent_id",
                "node_id",
                "run_id",
                "sender_display_name",
                "display_name",
                "agent_display_name",
            ):
                if key in prior and key not in base:
                    base[key] = prior[key]
    # bugfix-365: when gateway crashed before emitting `relay.processing`, the
    # event-history fallback above yields nothing — the failed payload then had no
    # `agent_id` / `sender_display_name`, and the downstream synthetic mapper fell
    # back to the literal "Agent" sender label. Recover identity from the messages
    # table so the failure is correctly attributed even on this edge path.
    if "agent_id" not in base or "sender_display_name" not in base:
        identity = _agent_identity_from_message_row(
            connection=connection, message_id=message_id
        )
        if identity is not None:
            agent_id, display_name = identity
            base.setdefault("agent_id", agent_id)
            if display_name is not None:
                base.setdefault("sender_display_name", display_name)
    return base


def _agent_identity_from_message_row(
    *,
    connection: sqlite3.Connection,
    message_id: str,
) -> tuple[str, str | None] | None:
    """Recover (agent_id, display_name) from a message row whose sender is an agent user."""
    row = connection.execute(
        """
        SELECT users.username AS username, users.display_name AS display_name
        FROM messages
        LEFT JOIN users ON users.id = messages.sender_user_id
        WHERE messages.id = ?
        """,
        (message_id,),
    ).fetchone()
    if row is None:
        return None
    username = row["username"]
    if username is None or not str(username).startswith("agent:"):
        return None
    agent_id = str(username)[len("agent:") :].strip()
    if not agent_id:
        return None
    display_name = row["display_name"]
    return agent_id, (str(display_name) if display_name is not None else None)


def _backfill_failure_detail_into_message_content(
    *,
    connection: sqlite3.Connection,
    message_id: str,
    detail_text: str,
) -> None:
    """Write the failure detail into the message content so the failed bubble renders it."""
    row = connection.execute(
        "SELECT content FROM messages WHERE id = ?",
        (message_id,),
    ).fetchone()
    if row is None:
        return
    existing = row["content"] if row["content"] is not None else ""
    existing_stripped = existing.strip()
    if not existing_stripped:
        new_content = detail_text
    elif f"[error] {detail_text}" in existing:
        return
    else:
        new_content = f"{existing}\n\n[error] {detail_text}"
    with connection:
        connection.execute(
            "UPDATE messages SET content = ? WHERE id = ?",
            (new_content, message_id),
        )


async def run_relay_watchdog(
    *,
    connection: sqlite3.Connection,
    event_repository: EventRepository,
    interval_seconds: int = 30,
    timeout_seconds: int = 120,
) -> None:
    """Background task: sweep stuck `running` messages every `interval_seconds`.

    Cancellation via `asyncio.Task.cancel` is the normal stop path; the FastAPI
    lifespan owns the task handle and cancels on shutdown.
    """
    while True:
        try:
            scan_and_fail_stuck_running_messages(
                connection=connection,
                event_repository=event_repository,
                timeout_seconds=timeout_seconds,
            )
        except Exception:  # noqa: BLE001
            logger.exception("relay_watchdog: sweep crashed; continuing after sleep")
        await asyncio.sleep(interval_seconds)
