"""SQLite repositories for IM users, conversations, and messages."""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from IM.models import Conversation, Message, User


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
        with self._connection:
            self._connection.execute(
                "INSERT INTO users(id, username, display_name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, display_name, created_at),
            )
        return User(
            id=user_id,
            username=username,
            display_name=display_name,
            created_at=created_at,
        )

    def list_users(self) -> list[User]:
        """List users in creation order.

        Returns:
            Users ordered by creation timestamp and insertion order.
        """
        rows = self._connection.execute(
            "SELECT id, username, display_name, created_at FROM users ORDER BY created_at, rowid"
        ).fetchall()
        return [
            User(
                id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
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
            ValueError: When participant list is empty or references missing users.
        """
        normalized_participants = list(dict.fromkeys(participant_ids))
        if not normalized_participants:
            raise ValueError("participant_ids must not be empty")
        if not title.strip():
            raise ValueError("title must be non-empty")

        placeholders = ",".join("?" for _ in normalized_participants)
        existing_rows = self._connection.execute(
            f"SELECT id FROM users WHERE id IN ({placeholders})",  # noqa: S608
            tuple(normalized_participants),
        ).fetchall()
        if len(existing_rows) != len(normalized_participants):
            raise ValueError("participant_ids contains unknown users")

        conversation_id = uuid4().hex
        created_at = _utc_now()
        with self._connection:
            self._connection.execute(
                "INSERT INTO conversations(id, title, created_at) VALUES (?, ?, ?)",
                (conversation_id, title, created_at),
            )
            self._connection.executemany(
                "INSERT INTO conversation_participants(conversation_id, user_id) VALUES (?, ?)",
                [(conversation_id, user_id) for user_id in normalized_participants],
            )
        return Conversation(
            id=conversation_id,
            title=title,
            participant_ids=normalized_participants,
            created_at=created_at,
        )

    def list_conversations(self) -> list[Conversation]:
        """List conversations with participant IDs.

        Returns:
            Conversations ordered by creation time.
        """
        conversation_rows = self._connection.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY created_at, rowid"
        ).fetchall()
        results: list[Conversation] = []
        for row in conversation_rows:
            participant_rows = self._connection.execute(
                """
                SELECT user_id
                FROM conversation_participants
                WHERE conversation_id = ?
                ORDER BY rowid
                """,
                (row["id"],),
            ).fetchall()
            results.append(
                Conversation(
                    id=row["id"],
                    title=row["title"],
                    participant_ids=[item["user_id"] for item in participant_rows],
                    created_at=row["created_at"],
                )
            )
        return results


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
    ) -> Message:
        """Create a message in a conversation.

        Args:
            conversation_id: Target conversation identifier.
            sender_user_id: Sender user identifier.
            content: Plain text body of the message.

        Returns:
            Created message entity.

        Raises:
            ValueError: When conversation/sender is missing or sender not in conversation.
        """
        if not content.strip():
            raise ValueError("content must be non-empty")

        conversation_exists = self._connection.execute(
            "SELECT 1 FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conversation_exists is None:
            raise ValueError("conversation_id not found")

        sender_exists = self._connection.execute(
            "SELECT 1 FROM users WHERE id = ?",
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
        if participant_exists is None:
            raise ValueError("sender_user_id is not a participant of conversation")

        message_id = uuid4().hex
        created_at = _utc_now()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO messages(id, conversation_id, sender_user_id, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, conversation_id, sender_user_id, content, created_at),
            )
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            content=content,
            created_at=created_at,
        )

    def list_messages(self, *, conversation_id: str) -> list[Message]:
        """List messages for a conversation in insertion order.

        Args:
            conversation_id: Target conversation identifier.

        Returns:
            Messages ordered by creation sequence.
        """
        rows = self._connection.execute(
            """
            SELECT id, conversation_id, sender_user_id, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY rowid
            """,
            (conversation_id,),
        ).fetchall()
        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                sender_user_id=row["sender_user_id"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


def _utc_now() -> str:
    """Return current UTC time formatted for storage."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
