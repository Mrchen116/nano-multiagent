"""SQLite repositories for IM users, conversations, and messages."""

from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import AgentProfile, Conversation, ConversationEvent, DeviceBindRequest, Message, NodeStatus, User


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
            owned_node_ids=[],
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
        return [self._row_to_user(row) for row in rows]

    def get_user(self, *, user_id: str) -> User | None:
        """Return one user with owned node ids, or None when missing."""
        row = self._connection.execute(
            "SELECT id, username, display_name, owner_id, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def update_user(self, *, user_id: str, display_name: str) -> User:
        """Update mutable user settings and return the latest snapshot."""
        if not display_name.strip():
            raise ValueError("display_name must be non-empty")
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (display_name, user_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("user_id not found")
        user = self.get_user(user_id=user_id)
        assert user is not None
        return user

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert one user row to a domain user including owned nodes."""
        node_rows = self._connection.execute(
            "SELECT node_id FROM nodes WHERE owner_id = ? ORDER BY rowid",
            (row["owner_id"],),
        ).fetchall()
        return User(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            owner_id=row["owner_id"],
            owned_node_ids=[item["node_id"] for item in node_rows],
            created_at=row["created_at"],
        )


class AgentProfileVersionConflictError(ValueError):
    """Raise when agent profile optimistic locking detects a stale version."""


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
            f"SELECT id, owner_id FROM users WHERE id IN ({placeholders})",  # noqa: S608
            tuple(normalized_participants),
        ).fetchall()
        if len(existing_rows) != len(normalized_participants):
            raise ValueError("participant_ids contains unknown users")

        conversation_id = uuid4().hex
        created_at = _utc_now()
        owner_id = existing_rows[0]["owner_id"]
        conversation_type = "direct" if len(normalized_participants) == 2 else "group"
        config_profile_version = self._resolve_config_profile_version(owner_id=owner_id, participant_ids=normalized_participants)
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
                    config_profile_version,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    config_profile_version,
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
            config_profile_version=config_profile_version,
            created_at=created_at,
        )

    def list_conversations(self) -> list[Conversation]:
        """List conversations with participant IDs.

        Returns:
            Conversations ordered by creation time.
        """
        conversation_rows = self._connection.execute(
            """
            SELECT id, title, type, owner_id, is_pinned, is_muted, unread_count, last_message_at, config_profile_version, created_at
            FROM conversations
            ORDER BY created_at, rowid
            """
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
                    type=row["type"],
                    owner_id=row["owner_id"],
                    is_pinned=bool(row["is_pinned"]),
                    is_muted=bool(row["is_muted"]),
                    unread_count=int(row["unread_count"]),
                    last_message_at=row["last_message_at"],
                    config_profile_version=row["config_profile_version"],
                    created_at=row["created_at"],
                )
            )
        return results

    def _resolve_config_profile_version(self, *, owner_id: str, participant_ids: list[str]) -> int | None:
        """Snapshot the latest agent profile version for new agent-facing conversations."""
        if not participant_ids:
            return None
        rows = self._connection.execute(
            f"SELECT profile_version FROM agent_profiles WHERE agent_id IN ({','.join('?' for _ in participant_ids)}) ORDER BY rowid LIMIT 1",  # noqa: S608
            tuple(participant_ids),
        ).fetchall()
        if not rows:
            return None
        return int(rows[0]["profile_version"])


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

        if not conversation_exists["owner_id"]:
            self._connection.execute(
                "UPDATE conversations SET owner_id = ? WHERE id = ?",
                (sender_exists["owner_id"], conversation_id),
            )
            conversation_exists = self._connection.execute(
                "SELECT owner_id FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()

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
        final_status = "completed"
        sender_type = "user"
        attachments_json = json.dumps([], ensure_ascii=True, separators=(",", ":"))
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
                    "attachments": [],
                },
            )
            self._connection.execute(
                "UPDATE messages SET delivery_status = ? WHERE id = ?",
                (final_status, message_id),
            )
            self._connection.execute(
                "UPDATE conversations SET last_message_at = ? WHERE id = ?",
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
                    "attachments": [],
                },
            )
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            sender_type=sender_type,
            content=content,
            attachments=[],
            delivery_status=final_status,
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
            SELECT id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at
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
                sender_type=row["sender_type"],
                content=row["content"],
                attachments=_decode_attachments(row["attachments_json"]),
                delivery_status=row["delivery_status"],
                created_at=row["created_at"],
            )
            for row in rows
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


class AgentProfileRepository:
    """Persist and query agent configuration profiles."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_profiles(self) -> list[AgentProfile]:
        """List agent profiles in stable creation order."""
        rows = self._connection.execute(
            """
            SELECT agent_id, owner_id, display_name, description, system_prompt, skills_json,
                   tool_allowlist_json, group_reply_policy, default_model, profile_version
            FROM agent_profiles
            ORDER BY created_at, rowid
            """
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile(self, *, agent_id: str) -> AgentProfile | None:
        """Return one agent profile, or None when it does not exist."""
        row = self._connection.execute(
            """
            SELECT agent_id, owner_id, display_name, description, system_prompt, skills_json,
                   tool_allowlist_json, group_reply_policy, default_model, profile_version
            FROM agent_profiles
            WHERE agent_id = ?
            """,
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def upsert_profile(
        self,
        *,
        agent_id: str,
        owner_id: str,
        display_name: str,
        description: str,
        system_prompt: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
    ) -> AgentProfile:
        """Create or replace one seed profile without optimistic locking."""
        created_at = _utc_now()
        skills_json = _encode_json_list(skills)
        tool_allowlist_json = _encode_json_list(tool_allowlist)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO agent_profiles(
                    agent_id, owner_id, display_name, description, system_prompt,
                    skills_json, tool_allowlist_json, group_reply_policy,
                    default_model, profile_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    display_name = excluded.display_name,
                    description = excluded.description,
                    system_prompt = excluded.system_prompt,
                    skills_json = excluded.skills_json,
                    tool_allowlist_json = excluded.tool_allowlist_json,
                    group_reply_policy = excluded.group_reply_policy,
                    default_model = excluded.default_model,
                    updated_at = excluded.updated_at
                """,
                (
                    agent_id,
                    owner_id,
                    display_name,
                    description,
                    system_prompt,
                    skills_json,
                    tool_allowlist_json,
                    group_reply_policy,
                    default_model,
                    1,
                    created_at,
                    created_at,
                ),
            )
        profile = self.get_profile(agent_id=agent_id)
        assert profile is not None
        return profile

    def update_profile(
        self,
        *,
        agent_id: str,
        profile_version: int,
        display_name: str,
        description: str,
        system_prompt: str,
        skills: list[str],
        tool_allowlist: list[str],
        group_reply_policy: str,
        default_model: str | None,
    ) -> AgentProfile:
        """Update a profile with optimistic locking on profile_version."""
        current = self.get_profile(agent_id=agent_id)
        if current is None:
            raise ValueError("agent_id not found")
        if current.profile_version != profile_version:
            raise AgentProfileVersionConflictError("profile_version conflict")
        updated_at = _utc_now()
        next_version = current.profile_version + 1
        with self._connection:
            self._connection.execute(
                """
                UPDATE agent_profiles
                SET display_name = ?,
                    description = ?,
                    system_prompt = ?,
                    skills_json = ?,
                    tool_allowlist_json = ?,
                    group_reply_policy = ?,
                    default_model = ?,
                    profile_version = ?,
                    updated_at = ?
                WHERE agent_id = ?
                """,
                (
                    display_name,
                    description,
                    system_prompt,
                    _encode_json_list(skills),
                    _encode_json_list(tool_allowlist),
                    group_reply_policy,
                    default_model,
                    next_version,
                    updated_at,
                    agent_id,
                ),
            )
        updated = self.get_profile(agent_id=agent_id)
        assert updated is not None
        return updated

    def reassign_owner_by_node(self, *, node_id: str, owner_id: str) -> None:
        """Assign all node-local agents to the bound user owner."""
        with self._connection:
            self._connection.execute(
                "UPDATE agent_profiles SET owner_id = ? WHERE node_id = ?",
                (owner_id, node_id),
            )

    def _row_to_profile(self, row: sqlite3.Row) -> AgentProfile:
        """Convert one storage row to a domain agent profile."""
        return AgentProfile(
            agent_id=row["agent_id"],
            owner_id=row["owner_id"],
            display_name=row["display_name"],
            description=row["description"],
            system_prompt=row["system_prompt"],
            skills=_decode_string_list(row["skills_json"]),
            tool_allowlist=_decode_string_list(row["tool_allowlist_json"]),
            group_reply_policy=row["group_reply_policy"],
            default_model=row["default_model"],
            profile_version=int(row["profile_version"]),
        )


class NodeRepository:
    """Persist and query gateway node ownership and status."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_node(
        self,
        *,
        node_id: str,
        node_name: str,
        status: str = "offline",
        version: str = "",
        owner_id: str | None = None,
    ) -> NodeStatus:
        """Create or update a node row and return the stored snapshot."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO nodes(node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    owner_id = COALESCE(excluded.owner_id, nodes.owner_id),
                    node_name = excluded.node_name,
                    status = excluded.status,
                    version = excluded.version
                """,
                (node_id, owner_id, node_name, status, "", 0, version, None),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def get_node(self, *, node_id: str) -> NodeStatus | None:
        """Return one node snapshot, or None when missing."""
        row = self._connection.execute(
            "SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version, last_error FROM nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return NodeStatus(
            node_id=row["node_id"],
            owner_id=row["owner_id"] or "",
            node_name=row["node_name"],
            status=row["status"],
            last_heartbeat_at=row["last_heartbeat_at"],
            agent_count=int(row["agent_count"]),
            version=row["version"],
            last_error=row["last_error"],
        )

    def assign_owner(self, *, node_id: str, owner_id: str) -> NodeStatus:
        """Bind a node to an owner and return the updated snapshot."""
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE nodes SET owner_id = ? WHERE node_id = ?",
                (owner_id, node_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("node_id not found")
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node


class BindRepository:
    """Persist and query device binding requests."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_bind_request(self, *, node_id: str, bind_base_url: str) -> DeviceBindRequest:
        """Create a pending bind request and return its browser URL."""
        bind_id = uuid4().hex
        bind_token = uuid4().hex
        created_at = _utc_now()
        bind_url = f"{bind_base_url.rstrip('/')}?token={bind_token}"
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO bind_requests(bind_id, node_id, user_id, status, bind_token, bind_url, created_at, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (bind_id, node_id, None, "pending", bind_token, bind_url, created_at, None),
            )
        request = self.get_bind_request(bind_id=bind_id)
        assert request is not None
        return request

    def get_bind_request(self, *, bind_id: str) -> DeviceBindRequest | None:
        """Return one bind request by id, or None when missing."""
        row = self._connection.execute(
            "SELECT bind_id, node_id, user_id, status, bind_token, bind_url, created_at, confirmed_at FROM bind_requests WHERE bind_id = ?",
            (bind_id,),
        ).fetchone()
        if row is None:
            return None
        return DeviceBindRequest(
            bind_id=row["bind_id"],
            node_id=row["node_id"],
            user_id=row["user_id"],
            status=row["status"],
            bind_token=row["bind_token"],
            bind_url=row["bind_url"],
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
        )

    def confirm_bind_request(self, *, bind_id: str, user_id: str) -> DeviceBindRequest:
        """Mark one pending bind request as confirmed for a user."""
        confirmed_at = _utc_now()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE bind_requests
                SET user_id = ?, status = ?, confirmed_at = ?
                WHERE bind_id = ? AND status = 'pending'
                """,
                (user_id, "confirmed", confirmed_at, bind_id),
            )
        if cursor.rowcount == 0:
            existing = self.get_bind_request(bind_id=bind_id)
            if existing is None:
                raise ValueError("bind_id not found")
            raise ValueError("bind request already confirmed")
        request = self.get_bind_request(bind_id=bind_id)
        assert request is not None
        return request


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


def _encode_json_list(values: list[str]) -> str:
    """Encode string lists with a stable JSON representation."""
    return json.dumps([str(item) for item in values], ensure_ascii=True, separators=(",", ":"))


def _decode_string_list(raw_value: str) -> list[str]:
    """Decode a JSON list into a list of strings."""
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded]


def _decode_attachments(raw_value: str) -> list[str]:
    """Decode attachments JSON into a stable list shape."""
    return _decode_string_list(raw_value)


def _utc_now() -> str:
    """Return current UTC time formatted for storage."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
