"""Application service for idempotent IM relay delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import Message, RelayTask


@dataclass(frozen=True, slots=True)
class RelayEnqueueResult:
    """Describe the outcome of enqueueing one relay task."""

    relay_task: RelayTask
    created: bool


class RelayService:
    """Create and update idempotent relay tasks for gateway delivery.

    Args:
        connection: SQLite connection shared with the IM app lifecycle.

    Notes:
        Relay task uniqueness is enforced by ``idempotency_key`` so retries do not
        create duplicate downstream deliveries.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def enqueue_message_relay(
        self,
        *,
        message: Message,
        target_node_id: str,
        idempotency_key: str,
        sender_user_id: str,
    ) -> RelayEnqueueResult:
        """Create or return an existing relay task for one IM message.

        Args:
            message: Persisted message that should be relayed to a gateway node.
            target_node_id: Gateway node that should receive the relay.
            idempotency_key: Stable retry key for the logical relay request.
            sender_user_id: Human sender identifier copied into the relay payload.

        Returns:
            RelayEnqueueResult with the canonical task and whether it was newly created.

        Raises:
            ValueError: When target_node_id or idempotency_key is blank.
        """
        if not target_node_id.strip():
            raise ValueError("target_node_id must be non-empty")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty")

        existing = self.get_task_by_idempotency_key(idempotency_key=idempotency_key)
        if existing is not None:
            return RelayEnqueueResult(relay_task=existing, created=False)

        created_at = _utc_now()
        relay_task_id = uuid4().hex
        payload = {
            "idempotency_key": idempotency_key,
            "conversation_id": message.conversation_id,
            "message": {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender_user_id": sender_user_id,
                "sender_type": message.sender_type,
                "content": message.content,
                "attachments": list(message.attachments),
                "created_at": message.created_at,
            },
        }
        payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with self._connection:
            try:
                self._connection.execute(
                    """
                    INSERT INTO relay_tasks(
                        relay_task_id,
                        message_id,
                        conversation_id,
                        target_node_id,
                        payload_json,
                        idempotency_key,
                        status,
                        receipt_status,
                        receipt_detail,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        relay_task_id,
                        message.id,
                        message.conversation_id,
                        target_node_id,
                        payload_json,
                        idempotency_key,
                        "pending",
                        None,
                        None,
                        created_at,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError:
                existing = self.get_task_by_idempotency_key(idempotency_key=idempotency_key)
                if existing is None:  # pragma: no cover - defensive consistency guard
                    raise
                return RelayEnqueueResult(relay_task=existing, created=False)
        created = self.get_task_by_idempotency_key(idempotency_key=idempotency_key)
        assert created is not None
        return RelayEnqueueResult(relay_task=created, created=True)

    def get_task_by_idempotency_key(self, *, idempotency_key: str) -> RelayTask | None:
        """Return the canonical relay task for one idempotency key if present."""
        row = self._connection.execute(
            """
            SELECT relay_task_id, message_id, conversation_id, target_node_id, payload_json,
                   idempotency_key, status, receipt_status, receipt_detail, created_at, updated_at
            FROM relay_tasks
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_relay_task(row)

    def mark_dispatched(self, *, relay_task_id: str) -> RelayTask:
        """Move one relay task from pending to dispatched after websocket push."""
        updated_at = _utc_now()
        with self._connection:
            self._connection.execute(
                "UPDATE relay_tasks SET status = ?, updated_at = ? WHERE relay_task_id = ?",
                ("dispatched", updated_at, relay_task_id),
            )
        task = self.get_task(relay_task_id=relay_task_id)
        assert task is not None
        return task

    def apply_delivery_receipt(
        self,
        *,
        relay_task_id: str,
        delivery_status: str,
        detail: str | None,
    ) -> RelayTask:
        """Apply a gateway delivery receipt to an existing relay task."""
        normalized = delivery_status.strip().lower()
        if normalized not in {"sent", "completed", "failed"}:
            raise ValueError("delivery_status must be one of sent/completed/failed")
        status = "failed" if normalized == "failed" else normalized
        updated_at = _utc_now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE relay_tasks
                SET status = ?, receipt_status = ?, receipt_detail = ?, updated_at = ?
                WHERE relay_task_id = ?
                """,
                (status, normalized, detail, updated_at, relay_task_id),
            )
        task = self.get_task(relay_task_id=relay_task_id)
        if task is None:
            raise ValueError("relay_task_id not found")
        return task

    def get_task(self, *, relay_task_id: str) -> RelayTask | None:
        """Return one relay task by primary key if present."""
        row = self._connection.execute(
            """
            SELECT relay_task_id, message_id, conversation_id, target_node_id, payload_json,
                   idempotency_key, status, receipt_status, receipt_detail, created_at, updated_at
            FROM relay_tasks
            WHERE relay_task_id = ?
            """,
            (relay_task_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_relay_task(row)


def _row_to_relay_task(row: sqlite3.Row) -> RelayTask:
    payload = json.loads(row["payload_json"])
    return RelayTask(
        relay_task_id=row["relay_task_id"],
        message_id=row["message_id"],
        conversation_id=row["conversation_id"],
        target_node_id=row["target_node_id"],
        payload=payload,
        idempotency_key=row["idempotency_key"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        receipt_status=row["receipt_status"],
        receipt_detail=row["receipt_detail"],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
