"""SQLite repositories for IM users, conversations, and messages."""

from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import Attachment, Conversation, ConversationEvent, Message, User


class UserRepository:
    """Persist and query chat users."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

    def create_user(self, *, username: str, display_name: str) -> User:
        """Create a user record.

        Args:
            username: Stable unique username for the user.
            display_name: Display name shown in conversation UI.

        Returns:
            Created user entity.

        Raises:
            ValueError: When username or display_name is blank.
        """
        if not username.strip() or not display_name.strip():
            raise ValueError("username and display_name must be non-empty")

        user_id = uuid4().hex
        created_at = _utc_now()
        owner_id = user_id
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO users(id, username, display_name, owner_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, display_name, owner_id, created_at),
            )
        return User(
            id=user_id,
            username=username,
            display_name=display_name,
            owner_id=owner_id,
            created_at=created_at,
        )

    def list_users(self) -> list[User]:
        """List users in creation order.

        Returns:
            Users ordered by creation timestamp and insertion order.
        """
        rows = self._connection.execute(
            "SELECT id, username, display_name, owner_id, created_at FROM users ORDER BY created_at, rowid"
        ).fetchall()
        return [
            User(
                id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
                owner_id=row["owner_id"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


class ConversationRepository:
    """Persist and query conversations and participants."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

    def create_conversation(self, *, title: str, participant_ids: list[str]) -> Conversation:
        """Create a conversation with participant membership.

        Args:
            title: Human-readable conversation title.
            participant_ids: User IDs that belong to the conversation.

        Returns:
            Created conversation entity.

        Raises:
            ValueError: When participant list is empty, references missing users, or mixes owners.
        """
        normalized_participants = list(dict.fromkeys(participant_ids))
        if not normalized_participants:
            raise ValueError("participant_ids must not be empty")
        if not title.strip():
            raise ValueError("title must be non-empty")

        placeholders = ",".join("?" for _ in normalized_participants)
        existing_rows = self._connection.execute(
            f"SELECT id, owner_id FROM users WHERE id IN ({placeholders})",  # noqa: S608
            tuple(normalized_participants),
        ).fetchall()
        if len(existing_rows) != len(normalized_participants):
            raise ValueError("participant_ids contains unknown users")

        owner_ids = {str(row["owner_id"]) for row in existing_rows}
        conversation_id = uuid4().hex
        created_at = _utc_now()
        owner_id = uuid4().hex if len(owner_ids) > 1 else next(iter(owner_ids))
        conversation_type = "direct" if len(normalized_participants) == 2 else "group"
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO conversations(
                    id,
                    title,
                    type,
                    owner_id,
                    is_pinned,
                    is_muted,
                    unread_count,
                    last_message_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    title,
                    conversation_type,
                    owner_id,
                    0,
                    0,
                    0,
                    None,
                    created_at,
                ),
            )
            self._connection.executemany(
                "INSERT INTO conversation_participants(conversation_id, user_id) VALUES (?, ?)",
                [(conversation_id, user_id) for user_id in normalized_participants],
            )
        return Conversation(
            id=conversation_id,
            title=title,
            participant_ids=normalized_participants,
            type=conversation_type,
            owner_id=owner_id,
            is_pinned=False,
            is_muted=False,
            unread_count=0,
            last_message_at=None,
            created_at=created_at,
        )

    def get_conversation(self, *, conversation_id: str) -> Conversation | None:
        """Load one conversation with participants."""
        row = self._connection.execute(
            """
            SELECT id, title, type, owner_id, is_pinned, is_muted, unread_count, last_message_at, created_at
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_conversation(row)

    def update_conversation(
        self,
        *,
        conversation_id: str,
        title: str | None,
        is_pinned: bool | None,
        is_muted: bool | None,
    ) -> Conversation:
        """Update mutable conversation metadata and return the new snapshot."""
        existing = self.get_conversation(conversation_id=conversation_id)
        if existing is None:
            raise ValueError("conversation_id not found")
        next_title = existing.title if title is None else title.strip()
        if not next_title:
            raise ValueError("title must be non-empty")
        next_is_pinned = existing.is_pinned if is_pinned is None else is_pinned
        next_is_muted = existing.is_muted if is_muted is None else is_muted
        with self._connection:
            self._connection.execute(
                """
                UPDATE conversations
                SET title = ?, is_pinned = ?, is_muted = ?
                WHERE id = ?
                """,
                (next_title, int(next_is_pinned), int(next_is_muted), conversation_id),
            )
        updated = self.get_conversation(conversation_id=conversation_id)
        assert updated is not None
        return updated

    def list_conversations(self) -> list[Conversation]:
        """List conversations with participant IDs.

        Returns:
            Conversations ordered by pinned-first then last activity then creation time.
        """
        conversation_rows = self._connection.execute(
            """
            SELECT id, title, type, owner_id, is_pinned, is_muted, unread_count, last_message_at, created_at
            FROM conversations
            ORDER BY is_pinned DESC, COALESCE(last_message_at, created_at) DESC, rowid DESC
            """
        ).fetchall()
        return [self._row_to_conversation(row) for row in conversation_rows]

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert one conversation row into a domain model with participants."""
        participant_rows = self._connection.execute(
            """
            SELECT user_id
            FROM conversation_participants
            WHERE conversation_id = ?
            ORDER BY rowid
            """,
            (row["id"],),
        ).fetchall()
        return Conversation(
            id=row["id"],
            title=row["title"],
            participant_ids=[item["user_id"] for item in participant_rows],
            type=row["type"],
            owner_id=row["owner_id"],
            is_pinned=bool(row["is_pinned"]),
            is_muted=bool(row["is_muted"]),
            unread_count=int(row["unread_count"]),
            last_message_at=row["last_message_at"],
            created_at=row["created_at"],
        )


class MessageRepository:
    """Persist and query conversation messages."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

    def create_message(
        self,
        *,
        conversation_id: str,
        sender_user_id: str,
        content: str,
        sender_type: str = "user",
        attachments: list[Attachment] | None = None,
    ) -> Message:
        """Create a message in a conversation.

        Args:
            conversation_id: Target conversation identifier.
            sender_user_id: Sender user identifier.
            content: Plain text body of the message.
            sender_type: Sender kind; must be user, agent, or system.
            attachments: Attachment descriptors stored alongside the message.

        Returns:
            Created message entity.

        Raises:
            ValueError: When conversation/sender is missing, owner scope mismatches, sender type is invalid,
                or sender is not a participant for user-originated messages.
        """
        if not content.strip():
            raise ValueError("content must be non-empty")
        if sender_type not in {"user", "agent", "system"}:
            raise ValueError("sender_type must be one of: user, agent, system")

        normalized_attachments = _normalize_attachments(attachments)
        conversation_exists = self._connection.execute(
            "SELECT owner_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conversation_exists is None:
            raise ValueError("conversation_id not found")

        sender_exists = self._connection.execute(
            "SELECT owner_id FROM users WHERE id = ?",
            (sender_user_id,),
        ).fetchone()
        if sender_exists is None:
            raise ValueError("sender_user_id not found")
        participant_exists = self._connection.execute(
            """
            SELECT 1
            FROM conversation_participants
            WHERE conversation_id = ? AND user_id = ?
            """,
            (conversation_id, sender_user_id),
        ).fetchone()
        if participant_exists is None and str(sender_exists["owner_id"]) != str(conversation_exists["owner_id"]):
            raise ValueError("sender_user_id is outside conversation owner scope")


        if sender_type == "user" and participant_exists is None:
            raise ValueError("sender_user_id is not a participant of conversation")

        message_id = uuid4().hex
        created_at = _utc_now()
        final_status = "completed"
        attachments_json = _encode_attachments(normalized_attachments)
        event_attachments = [_attachment_to_dict(item) for item in normalized_attachments]
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO messages(
                    id,
                    conversation_id,
                    sender_user_id,
                    sender_type,
                    content,
                    attachments_json,
                    delivery_status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    sender_user_id,
                    sender_type,
                    content,
                    attachments_json,
                    "sent",
                    created_at,
                ),
            )
            self._insert_event(
                conversation_id=conversation_id,
                message_id=message_id,
                event_type="message.sent",
                delivery_status="sent",
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "sender_user_id": sender_user_id,
                    "sender_type": sender_type,
                    "attachments": event_attachments,
                },
            )
            self._connection.execute(
                "UPDATE messages SET delivery_status = ? WHERE id = ?",
                (final_status, message_id),
            )
            # Web IM unread_count is tracked per owner-scoped conversation in V1. Every persisted message bumps
            # the aggregate counter; read/ack semantics can later decrement it without changing this write path.
            self._connection.execute(
                "UPDATE conversations SET last_message_at = ?, unread_count = unread_count + 1 WHERE id = ?",
                (created_at, conversation_id),
            )
            self._insert_event(
                conversation_id=conversation_id,
                message_id=message_id,
                event_type="message.delivered",
                delivery_status=final_status,
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "sender_user_id": sender_user_id,
                    "sender_type": sender_type,
                    "attachments": event_attachments,
                },
            )
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            sender_type=sender_type,
            content=content,
            attachments=normalized_attachments,
            delivery_status=final_status,
            created_at=created_at,
        )

    def list_messages(
        self,
        *,
        conversation_id: str,
        limit: int = 50,
        before_message_id: str | None = None,
    ) -> list[Message]:
        """List messages for a conversation in insertion order.

        Args:
            conversation_id: Target conversation identifier.
            limit: Maximum number of recent messages to return.
            before_message_id: Exclusive cursor; return messages older than this message.

        Returns:
            Messages ordered from oldest to newest within the selected page.
        """
        bounded_limit = max(1, min(limit, 200))
        params: list[object] = [conversation_id]
        cursor_clause = ""
        if before_message_id is not None:
            cursor_row = self._connection.execute(
                "SELECT rowid FROM messages WHERE id = ? AND conversation_id = ?",
                (before_message_id, conversation_id),
            ).fetchone()
            if cursor_row is None:
                raise ValueError("before_message_id not found")
            cursor_clause = " AND rowid < ?"
            params.append(int(cursor_row["rowid"]))
        params.append(bounded_limit)
        rows = self._connection.execute(
            f"""
            SELECT id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at
            FROM messages
            WHERE conversation_id = ?{cursor_clause}
            ORDER BY rowid DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        ordered_rows = list(reversed(rows))
        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                sender_user_id=row["sender_user_id"],
                sender_type=row["sender_type"],
                content=row["content"],
                attachments=_decode_attachments(row["attachments_json"]),
                delivery_status=row["delivery_status"],
                created_at=row["created_at"],
            )
            for row in ordered_rows
        ]

    def _insert_event(
        self,
        *,
        conversation_id: str,
        message_id: str | None,
        event_type: str,
        delivery_status: str,
        payload: dict[str, object],
    ) -> int:
        """Insert one persisted event row and return SQLite event id."""
        created_at = _utc_now()
        cursor = self._connection.execute(
            """
            INSERT INTO conversation_events(
                conversation_id,
                message_id,
                event_type,
                delivery_status,
                payload_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                message_id,
                event_type,
                delivery_status,
                json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
                created_at,
            ),
        )
        return int(cursor.lastrowid)


class EventRepository:
    """Persist and query conversation events."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

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


def _attachment_to_dict(attachment: Attachment) -> dict[str, object]:
    """Convert one attachment dataclass to persisted/event payload shape."""
    payload: dict[str, object] = {"url": attachment.url}
    if attachment.content_type is not None:
        payload["content_type"] = attachment.content_type
    if attachment.file_name is not None:
        payload["file_name"] = attachment.file_name
    return payload


def _normalize_attachments(attachments: list[Attachment] | None) -> list[Attachment]:
    """Validate and normalize attachment payloads before persistence."""
    normalized = attachments or []
    results: list[Attachment] = []
    for item in normalized:
        url = item.url.strip()
        if not url:
            raise ValueError("attachments[].url must be non-empty")
        content_type = item.content_type.strip() if item.content_type else None
        file_name = item.file_name.strip() if item.file_name else None
        results.append(
            Attachment(
                url=url,
                content_type=content_type or None,
                file_name=file_name or None,
            )
        )
    return results


def _encode_attachments(attachments: list[Attachment]) -> str:
    """Encode attachments JSON with stable field ordering."""
    payload = [_attachment_to_dict(item) for item in attachments]
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _decode_attachments(raw_value: str) -> list[Attachment]:
    """Decode attachments JSON into a stable list shape."""
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    results: list[Attachment] = []
    for item in decoded:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        content_type = item.get("content_type")
        file_name = item.get("file_name")
        results.append(
            Attachment(
                url=url,
                content_type=str(content_type) if content_type not in {None, ""} else None,
                file_name=str(file_name) if file_name not in {None, ""} else None,
            )
        )
    return results


def _utc_now() -> str:
    """Return current UTC time formatted for storage."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
