"""SQLite repositories for IM users, conversations, and messages."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import sqlite3

from IM.domain.models import (
    ConversationEvent,
)
from IM.infra._helpers import (
    _optional_text,
    _preview_from_event,
)


from IM.infra._timestamps import utc_now
from IM.infra.repositories._event_rows import insert_event_row


@dataclass(frozen=True, slots=True)
class EventReplayResult:
    """Result of a browser user-stream resume query."""

    events: list[ConversationEvent]
    resync_required: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class RelayRunIdentity:
    """Persisted agent identity attached to one relay run."""

    relay_task_id: str | None
    agent_id: str | None


class EventRepository:
    """Persist and query conversation events."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        notify: Callable[[ConversationEvent], None] | None = None,
    ) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
            notify: 可选；持久化成功后同步通知用户流广播。
        """
        self._connection = connection
        self._notify = notify

    def append_event(
        self,
        *,
        conversation_id: str,
        message_id: str | None,
        event_type: str,
        delivery_status: str,
        payload: dict[str, object],
    ) -> ConversationEvent:
        """Persist one conversation event and return the stored row.

        Args:
            conversation_id: Conversation that should receive the event.
            message_id: Related message when the event is message-scoped.
            event_type: Logical SSE event name.
            delivery_status: User-visible delivery/progress status.
            payload: JSON-serializable event body.

        Returns:
            The stored conversation event including the generated event id.
        """
        created_at = utc_now()
        preview = _preview_from_event(event_type=event_type, payload=payload)
        with self._connection:
            event = insert_event_row(
                self._connection,
                conversation_id=conversation_id,
                message_id=message_id,
                event_type=event_type,
                delivery_status=delivery_status,
                payload=payload,
                created_at=created_at,
            )
            if preview is not None:
                self._connection.execute(
                    "UPDATE conversations SET last_message_preview = ?, last_message_at = ? WHERE id = ?",
                    (preview, created_at, conversation_id),
                )
        if self._notify is not None:
            self._notify(event)
        return event

    def update_message_delivery_status(
        self,
        *,
        message_id: str,
        delivery_status: str,
    ) -> None:
        """Update the canonical delivery status stored on one message row."""
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET delivery_status = ? WHERE id = ?",
                (delivery_status, message_id),
            )

    def get_latest_event_id(self, *, conversation_id: str) -> int:
        """Return the highest persisted event id for one conversation."""
        row = self._connection.execute(
            "SELECT MAX(event_id) AS latest_event_id FROM conversation_events WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None or row["latest_event_id"] is None:
            return 0
        return int(row["latest_event_id"])

    def list_events(
        self,
        *,
        conversation_id: str,
        after_event_id: int = 0,
        limit: int = 200,
    ) -> list[ConversationEvent]:
        """List events newer than the cursor for one conversation.

        Args:
            conversation_id: Target conversation identifier.
            after_event_id: Exclusive cursor; only events with bigger ids are returned.
            limit: Maximum number of events to return.

        Returns:
            Events ordered by event id ascending.
        """
        bounded_limit = max(1, min(limit, 500))
        rows = self._connection.execute(
            """
            SELECT event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at
            FROM conversation_events
            WHERE conversation_id = ? AND event_id > ?
            ORDER BY event_id
            LIMIT ?
            """,
            (conversation_id, after_event_id, bounded_limit),
        ).fetchall()
        return [
            ConversationEvent(
                event_id=int(row["event_id"]),
                conversation_id=row["conversation_id"],
                message_id=row["message_id"],
                event_type=row["event_type"],
                delivery_status=row["delivery_status"],
                payload_json=row["payload_json"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def recipient_user_ids(self, conversation_id: str) -> tuple[str, ...]:
        """Return users that should receive events for one conversation."""
        rows = self._connection.execute(
            "SELECT user_id FROM conversation_participants WHERE conversation_id = ? ORDER BY rowid",
            (conversation_id,),
        ).fetchall()
        return tuple(str(row["user_id"]) for row in rows)

    def global_max_event_id(self) -> int:
        """Return the highest event id across all conversations."""
        row = self._connection.execute(
            "SELECT MAX(event_id) AS m FROM conversation_events"
        ).fetchone()
        if row is None or row["m"] is None:
            return 0
        return int(row["m"])

    def list_events_for_user_resume(
        self,
        *,
        user_id: str,
        after_event_id: int,
        max_batch: int = 500,
        max_gap: int = 2000,
        replay_window_minutes: int = 15,
        up_to_event_id: int | None = None,
    ) -> EventReplayResult:
        """List owner-visible events inside one stable resume snapshot."""
        max_id = (
            self.global_max_event_id()
            if up_to_event_id is None
            else max(0, up_to_event_id)
        )
        if after_event_id > max_id:
            return EventReplayResult(
                events=[],
                resync_required=True,
                reason="cursor_ahead_of_event_store",
            )
        if after_event_id > 0 and max_id - after_event_id > max_gap:
            return EventReplayResult(
                events=[],
                resync_required=True,
                reason="event_gap_exceeded",
            )

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=replay_window_minutes)
        cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
        rows = self._connection.execute(
            """
            SELECT event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at
            FROM conversation_events
            WHERE event_id > ?
              AND event_id <= ?
              AND created_at >= ?
              AND conversation_id IN (
                SELECT conversation_id FROM conversation_participants WHERE user_id = ?
              )
            ORDER BY event_id
            LIMIT ?
            """,
            (after_event_id, max_id, cutoff_iso, user_id, max_batch),
        ).fetchall()
        user_max_row = self._connection.execute(
            """
            SELECT MAX(event_id) AS max_event_id
            FROM conversation_events
            WHERE event_id <= ?
              AND conversation_id IN (
                SELECT conversation_id FROM conversation_participants WHERE user_id = ?
            )
            """,
            (max_id, user_id),
        ).fetchone()
        user_max_id = (
            int(user_max_row["max_event_id"])
            if user_max_row is not None and user_max_row["max_event_id"] is not None
            else 0
        )
        if after_event_id > 0 and not rows and user_max_id > after_event_id:
            return EventReplayResult(
                events=[],
                resync_required=True,
                reason="cursor_stale_or_outside_replay_window",
            )
        return EventReplayResult(
            events=[self._row_to_event(row) for row in rows],
            resync_required=False,
            reason=None,
        )

    def relay_run_identities(
        self,
        *,
        conversation_id: str,
        up_to_event_id: int,
    ) -> dict[str, RelayRunIdentity]:
        """Resolve the latest persisted relay identity for each run."""
        rows = self._connection.execute(
            """
            SELECT payload_json
            FROM conversation_events
            WHERE conversation_id = ? AND event_type = ? AND event_id <= ?
            ORDER BY event_id
            """,
            (conversation_id, "relay.accepted", up_to_event_id),
        ).fetchall()
        identities: dict[str, RelayRunIdentity] = {}
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            run_id = _optional_text(payload.get("run_id"))
            if run_id is None:
                detail = _optional_text(payload.get("detail"))
                if detail is not None and detail.startswith("run_id="):
                    run_id = _optional_text(detail[len("run_id=") :])
            if run_id is None:
                continue
            identities[run_id] = RelayRunIdentity(
                relay_task_id=_optional_text(payload.get("relay_task_id")),
                agent_id=_optional_text(payload.get("agent_id")),
            )
        return identities

    def agent_display_names(self, agent_ids: set[str]) -> dict[str, str]:
        """Return non-empty display names for the requested agents."""
        if not agent_ids:
            return {}
        placeholders = ",".join("?" for _ in agent_ids)
        rows = self._connection.execute(
            f"SELECT agent_id, display_name FROM agent_profiles WHERE agent_id IN ({placeholders})",  # noqa: S608
            tuple(agent_ids),
        ).fetchall()
        return {
            str(row["agent_id"]): str(row["display_name"])
            for row in rows
            if row["agent_id"] is not None
            and row["display_name"] is not None
            and str(row["display_name"]).strip()
        }

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> ConversationEvent:
        return ConversationEvent(
            event_id=int(row["event_id"]),
            conversation_id=str(row["conversation_id"]),
            message_id=str(row["message_id"])
            if row["message_id"] is not None
            else None,
            event_type=str(row["event_type"]),
            delivery_status=str(row["delivery_status"]),
            payload_json=str(row["payload_json"]),
            created_at=str(row["created_at"]),
        )
