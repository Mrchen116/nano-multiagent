"""Transaction-neutral conversation event row primitive."""

from __future__ import annotations

import json
import sqlite3

from IM.domain.models import ConversationEvent


def insert_event_row(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    message_id: str | None,
    event_type: str,
    delivery_status: str,
    payload: dict[str, object],
    created_at: str,
) -> ConversationEvent:
    """Insert and map an event row inside the caller-owned transaction."""
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cursor = connection.execute(
        """
        INSERT INTO conversation_events(
            conversation_id, message_id, event_type, delivery_status, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            message_id,
            event_type,
            delivery_status,
            payload_json,
            created_at,
        ),
    )
    return ConversationEvent(
        event_id=int(cursor.lastrowid),
        conversation_id=conversation_id,
        message_id=message_id,
        event_type=event_type,
        delivery_status=delivery_status,
        payload_json=payload_json,
        created_at=created_at,
    )
