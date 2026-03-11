"""SQLite repositories for IM users, conversations, and messages."""

from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import AgentProfile, Attachment, Conversation, ConversationEvent, DeviceBindRequest, Message, NodeStatus, UsageMetric, User


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
            SELECT id, title, type, owner_id, is_pinned, is_muted, unread_count, last_message_at, config_profile_version, created_at
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
        profile_version = row["config_profile_version"] if "config_profile_version" in row.keys() else None
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
            config_profile_version=profile_version,
            created_at=row["created_at"],
        )

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
    """Persist and query gateway node ownership, center config, and status."""

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
        normalized_status = _normalize_node_status(status=status, last_error=None)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO nodes(
                    node_id,
                    owner_id,
                    node_name,
                    status,
                    last_heartbeat_at,
                    agent_count,
                    version,
                    relay_enabled,
                    reporting_enabled,
                    alias,
                    last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    owner_id = COALESCE(excluded.owner_id, nodes.owner_id),
                    node_name = excluded.node_name,
                    status = excluded.status,
                    version = excluded.version
                """,
                (node_id, owner_id, node_name, normalized_status, "", 0, version, 1, 1, None, None),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def record_gateway_registration(
        self,
        *,
        node_id: str,
        node_name: str,
        version: str,
        agent_count: int,
        owner_id: str | None = None,
    ) -> NodeStatus:
        """Persist node.register metadata as an online snapshot."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO nodes(
                    node_id,
                    owner_id,
                    node_name,
                    status,
                    last_heartbeat_at,
                    agent_count,
                    version,
                    relay_enabled,
                    reporting_enabled,
                    alias,
                    last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    owner_id = COALESCE(excluded.owner_id, nodes.owner_id),
                    node_name = excluded.node_name,
                    status = excluded.status,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    agent_count = excluded.agent_count,
                    version = excluded.version,
                    last_error = excluded.last_error
                """,
                (node_id, owner_id, node_name, "online", _utc_now(), max(agent_count, 0), version, 1, 1, None, None),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def record_heartbeat(
        self,
        *,
        node_id: str,
        reported_status: str | None,
        agent_count: int | None,
        last_error: str | None,
        version: str | None,
    ) -> NodeStatus:
        """Persist node.heartbeat payload and derive canonical status aggregation."""
        existing = self.get_node(node_id=node_id)
        if existing is None:
            raise ValueError("node_id not found")
        next_status = _normalize_node_status(status=reported_status, last_error=last_error)
        next_agent_count = existing.agent_count if agent_count is None else max(agent_count, 0)
        next_version = existing.version if version is None else version
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                SET status = ?, last_heartbeat_at = ?, agent_count = ?, version = ?, last_error = ?
                WHERE node_id = ?
                """,
                (next_status, _utc_now(), next_agent_count, next_version, last_error, node_id),
            )
        node = self.get_node(node_id=node_id)
        assert node is not None
        return node

    def list_nodes(self) -> list[NodeStatus]:
        """List node board snapshots in recency order."""
        rows = self._connection.execute(
            """
            SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version,
                   relay_enabled, reporting_enabled, alias, last_error
            FROM nodes
            ORDER BY CASE status WHEN 'online' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END,
                     COALESCE(last_heartbeat_at, '') DESC,
                     rowid DESC
            """
        ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def get_node(self, *, node_id: str) -> NodeStatus | None:
        """Return one node snapshot, or None when missing."""
        row = self._connection.execute(
            """
            SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version,
                   relay_enabled, reporting_enabled, alias, last_error
            FROM nodes WHERE node_id = ?
            """,
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

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

    def update_node_config(
        self,
        *,
        node_id: str,
        alias: str | None,
        relay_enabled: bool | None,
        reporting_enabled: bool | None,
    ) -> NodeStatus:
        """Update node center config and return the latest snapshot."""
        existing = self.get_node(node_id=node_id)
        if existing is None:
            raise ValueError("node_id not found")
        next_alias = existing.alias if alias is None else (alias.strip() or None)
        next_relay_enabled = existing.relay_enabled if relay_enabled is None else relay_enabled
        next_reporting_enabled = existing.reporting_enabled if reporting_enabled is None else reporting_enabled
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                SET alias = ?, relay_enabled = ?, reporting_enabled = ?
                WHERE node_id = ?
                """,
                (next_alias, int(next_relay_enabled), int(next_reporting_enabled), node_id),
            )
        updated = self.get_node(node_id=node_id)
        assert updated is not None
        return updated

    def mark_disconnected(self, *, node_id: str) -> NodeStatus | None:
        """Mark a node offline when its websocket disconnects."""
        existing = self.get_node(node_id=node_id)
        if existing is None:
            return None
        with self._connection:
            self._connection.execute(
                "UPDATE nodes SET status = ? WHERE node_id = ?",
                ("offline", node_id),
            )
        return self.get_node(node_id=node_id)

    def _row_to_node(self, row: sqlite3.Row) -> NodeStatus:
        """Convert one row into a node status model."""
        return NodeStatus(
            node_id=row["node_id"],
            owner_id=row["owner_id"] or "",
            node_name=row["node_name"],
            status=row["status"],
            last_heartbeat_at=row["last_heartbeat_at"],
            agent_count=int(row["agent_count"]),
            version=row["version"],
            relay_enabled=bool(row["relay_enabled"]),
            reporting_enabled=bool(row["reporting_enabled"]),
            alias=row["alias"],
            last_error=row["last_error"],
        )


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


class UsageMetricsRepository:
    """Persist and aggregate token/turn usage metrics for IM board APIs."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def record_usage(
        self,
        *,
        owner_id: str | None,
        conversation_id: str | None,
        agent_id: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        turns: int = 1,
    ) -> None:
        """Persist one usage sample emitted by IM-visible activity."""
        normalized_prompt = max(prompt_tokens, 0)
        normalized_completion = max(completion_tokens, 0)
        normalized_turns = max(turns, 0)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO usage_metrics(
                    owner_id,
                    conversation_id,
                    agent_id,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    turns,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id,
                    conversation_id,
                    agent_id,
                    normalized_prompt,
                    normalized_completion,
                    normalized_prompt + normalized_completion,
                    normalized_turns,
                    _utc_now(),
                ),
            )

    def list_usage_metrics(
        self,
        *,
        owner_id: str | None = None,
        conversation_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[UsageMetric]:
        """Return aggregated usage grouped by owner, conversation, and agent scopes."""
        filters: list[str] = []
        params: list[object] = []
        if owner_id is not None:
            filters.append("owner_id = ?")
            params.append(owner_id)
        if conversation_id is not None:
            filters.append("conversation_id = ?")
            params.append(conversation_id)
        if agent_id is not None:
            filters.append("agent_id = ?")
            params.append(agent_id)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self._connection.execute(
            f"""
            SELECT owner_id, conversation_id, agent_id,
                   SUM(turns) AS turns,
                   SUM(prompt_tokens) AS prompt_tokens,
                   SUM(completion_tokens) AS completion_tokens,
                   SUM(total_tokens) AS total_tokens,
                   MAX(created_at) AS last_used_at
            FROM usage_metrics
            {where_clause}
            GROUP BY owner_id, conversation_id, agent_id
            ORDER BY last_used_at DESC, rowid DESC
            """,
            tuple(params),
        ).fetchall()
        metrics: list[UsageMetric] = []
        for row in rows:
            scope, scope_id = _resolve_usage_scope(
                owner_id=row["owner_id"],
                conversation_id=row["conversation_id"],
                agent_id=row["agent_id"],
            )
            metrics.append(
                UsageMetric(
                    scope=scope,
                    scope_id=scope_id,
                    owner_id=row["owner_id"],
                    conversation_id=row["conversation_id"],
                    agent_id=row["agent_id"],
                    turns=int(row["turns"] or 0),
                    prompt_tokens=int(row["prompt_tokens"] or 0),
                    completion_tokens=int(row["completion_tokens"] or 0),
                    total_tokens=int(row["total_tokens"] or 0),
                    last_used_at=row["last_used_at"],
                )
            )
        return metrics


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


def _resolve_usage_scope(*, owner_id: str | None, conversation_id: str | None, agent_id: str | None) -> tuple[str, str | None]:
    """Choose the most specific scope label for one aggregated usage row."""
    if agent_id:
        return "agent", agent_id
    if conversation_id:
        return "conversation", conversation_id
    if owner_id:
        return "owner", owner_id
    return "global", None


def _normalize_node_status(*, status: str | None, last_error: str | None) -> str:
    """Collapse raw gateway state into the canonical node board statuses."""
    normalized = (status or "").strip().lower()
    if last_error:
        return "degraded"
    if normalized in {"online", "offline", "degraded"}:
        return normalized
    if normalized in {"error", "failed", "warning", "degraded_partial"}:
        return "degraded"
    if normalized in {"connected", "healthy", "ready"}:
        return "online"
    if normalized in {"disconnected", "unknown", "timeout"}:
        return "offline"
    return "online" if normalized else "offline"


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
