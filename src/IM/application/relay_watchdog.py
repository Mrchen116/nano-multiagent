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

from IM.infra.repositories import EventRepository

logger = logging.getLogger(__name__)


def scan_and_fail_stuck_running_messages(
    *,
    connection: sqlite3.Connection,
    event_repository: EventRepository,
    timeout_seconds: int = 300,
) -> int:
    """Find messages stuck in `running` past the cutoff, fail them, and push `relay.failed`.

    Args:
        connection: SQLite connection used to scan `messages` / `conversation_events`.
        event_repository: Used to append the synthetic `relay.failed` event so WS clients
            see the placeholder flip without an extra round trip.
        timeout_seconds: Age (relative to `messages.created_at`) past which a `running`
            message is considered orphaned. Default 5 minutes matches the issue's
            suggested window — long enough to cover normal LLM latency, short enough
            that the UI does not feel stuck.

    Returns:
        Number of messages flipped from `running` to `failed` in this pass.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat().replace("+00:00", "Z")
    rows = connection.execute(
        """
        SELECT id, conversation_id, created_at
        FROM messages
        WHERE delivery_status = 'running'
          AND created_at < ?
        """,
        (cutoff,),
    ).fetchall()
    if not rows:
        return 0

    flipped = 0
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
        "semantic": "relay_watchdog_timeout",
        "detail": f"relay timed out after {timeout_seconds}s with no completion event",
        "reason": "watchdog_timeout",
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
    if row is None:
        return base
    try:
        prior = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        return base
    if not isinstance(prior, dict):
        return base
    # Inherit relay_task_id / agent_id / node_id / run_id so synthetic_message_id matches.
    for key in ("relay_task_id", "agent_id", "node_id", "run_id", "sender_display_name", "display_name", "agent_display_name"):
        if key in prior and key not in base:
            base[key] = prior[key]
    return base


async def run_relay_watchdog(
    *,
    connection: sqlite3.Connection,
    event_repository: EventRepository,
    interval_seconds: int = 30,
    timeout_seconds: int = 300,
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
