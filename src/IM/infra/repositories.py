"""SQLite repositories for IM users, conversations, and messages."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from IM.domain.models import (
    Actor,
    AgentProfile,
    Attachment,
    Conversation,
    ConversationEvent,
    DeviceBindRequest,
    Message,
    NodeStatus,
    SettingsPolicy,
    ThinkingSegment,
    TokenUsage,
    ToolCall,
    UsageMetric,
    User,
)
from IM.infra.db import DEFAULT_SETTINGS_POLICIES
from IM.infra._helpers import (
    _optional_text,
    _preview_from_event,
)


class UserAlreadyExistsError(ValueError):
    """Raise when creating a user with a username that already exists."""


class RepositoryConstraintError(ValueError):
    """Raise when SQLite integrity constraints need API-safe translation."""


def _raise_constraint_error(error: sqlite3.IntegrityError) -> None:
    """Translate SQLite integrity failures into stable ValueError subclasses."""
    detail = str(error)
    if "users.username" in detail:
        raise UserAlreadyExistsError("username already exists") from error
    raise RepositoryConstraintError(detail) from error


class UserRepository:
    """Persist and query chat users."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

    _USER_SELECT_COLUMNS = (
        "id, username, display_name, owner_id, default_entry_node_id, "
        "password_hash, locale, created_at"
    )

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        password_hash: str | None = None,
        locale: str = "en",
    ) -> User:
        """Create a user record.

        Args:
            username: Stable unique username for the user.
            display_name: Display name shown in conversation UI.
            password_hash: Optional bcrypt hash used by the auth flow; None for legacy fixtures.
            locale: Initial UI locale; defaults to ``en``.

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
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO users(id, username, display_name, owner_id, default_entry_node_id, password_hash, locale, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        display_name,
                        owner_id,
                        None,
                        password_hash,
                        locale,
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            _raise_constraint_error(error)
        return User(
            id=user_id,
            username=username,
            display_name=display_name,
            owner_id=owner_id,
            owned_node_ids=[],
            default_entry_node_id=None,
            created_at=created_at,
            password_hash=password_hash,
            locale=locale,
        )

    def list_users(self) -> list[User]:
        """List users in creation order.

        Returns:
            Users ordered by creation timestamp and insertion order.
        """
        rows = self._connection.execute(
            f"SELECT {self._USER_SELECT_COLUMNS} FROM users ORDER BY created_at, rowid"
        ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, *, user_id: str) -> User | None:
        """Return one user with owned node ids, or None when missing."""
        row = self._connection.execute(
            f"SELECT {self._USER_SELECT_COLUMNS} FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_user_by_username(self, *, username: str) -> User | None:
        """Return one user by username (auth login lookup)."""
        row = self._connection.execute(
            f"SELECT {self._USER_SELECT_COLUMNS} FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def update_user(
        self,
        *,
        user_id: str,
        display_name: str,
        default_entry_node_id: str | None,
        locale: str | None = None,
    ) -> User:
        """Update mutable user settings and return the latest snapshot."""
        if not display_name.strip():
            raise ValueError("display_name must be non-empty")
        user = self.get_user(user_id=user_id)
        if user is None:
            raise ValueError("user_id not found")
        next_default_entry_node_id = default_entry_node_id
        if next_default_entry_node_id is not None:
            next_default_entry_node_id = next_default_entry_node_id.strip() or None
            if (
                next_default_entry_node_id
                and next_default_entry_node_id not in user.owned_node_ids
            ):
                raise ValueError("default_entry_node_id not owned by user")
        next_locale = user.locale if locale is None else locale.strip() or user.locale
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE users SET display_name = ?, default_entry_node_id = ?, locale = ? WHERE id = ?",
                (display_name, next_default_entry_node_id, next_locale, user_id),
            )
        if cursor.rowcount == 0:
            raise ValueError("user_id not found")
        user = self.get_user(user_id=user_id)
        assert user is not None
        return user

    def ensure_default_entry_node(self, *, user_id: str, node_id: str) -> User:
        """Set a user's default entry node when it is missing or no longer owned."""
        user = self.get_user(user_id=user_id)
        if user is None:
            raise ValueError("user_id not found")
        if user.default_entry_node_id in user.owned_node_ids:
            return user
        with self._connection:
            self._connection.execute(
                "UPDATE users SET default_entry_node_id = ? WHERE id = ?",
                (node_id, user_id),
            )
        updated = self.get_user(user_id=user_id)
        assert updated is not None
        return updated

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert one user row to a domain user including owned nodes."""
        node_rows = self._connection.execute(
            "SELECT node_id FROM nodes WHERE owner_id = ? ORDER BY rowid",
            (row["owner_id"],),
        ).fetchall()
        owned_node_ids = [item["node_id"] for item in node_rows]
        default_entry_node_id = row["default_entry_node_id"]
        if default_entry_node_id not in owned_node_ids:
            default_entry_node_id = owned_node_ids[0] if owned_node_ids else None
        row_keys = row.keys() if hasattr(row, "keys") else []
        password_hash = row["password_hash"] if "password_hash" in row_keys else None
        locale = row["locale"] if "locale" in row_keys and row["locale"] else "en"
        return User(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            owner_id=row["owner_id"],
            owned_node_ids=owned_node_ids,
            default_entry_node_id=default_entry_node_id,
            created_at=row["created_at"],
            password_hash=password_hash,
            locale=locale,
        )


class SettingsPolicyRepository:
    """Persist and query the singleton settings-policy document."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_policies(self) -> SettingsPolicy:
        """Return the singleton settings-policy row."""
        row = self._connection.execute(
            """
            SELECT default_model, max_turn_per_run, max_attachment_size_mb, retention_days, audit_level, rate_limit_per_min
            FROM settings_policies
            WHERE singleton_key = 'default'
            """
        ).fetchone()
        if row is None:
            row = self._reseed_default_policy_row()
        return SettingsPolicy(
            default_model=str(row["default_model"]),
            max_turn_per_run=int(row["max_turn_per_run"]),
            max_attachment_size_mb=int(row["max_attachment_size_mb"]),
            retention_days=int(row["retention_days"]),
            audit_level=str(row["audit_level"]),
            rate_limit_per_min=int(row["rate_limit_per_min"]),
        )

    def _reseed_default_policy_row(self) -> sqlite3.Row:
        """Recreate the singleton settings-policy row for older runtime databases."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO settings_policies(
                    singleton_key,
                    default_model,
                    max_turn_per_run,
                    max_attachment_size_mb,
                    retention_days,
                    audit_level,
                    rate_limit_per_min
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(singleton_key) DO NOTHING
                """,
                (
                    DEFAULT_SETTINGS_POLICIES["singleton_key"],
                    DEFAULT_SETTINGS_POLICIES["default_model"],
                    DEFAULT_SETTINGS_POLICIES["max_turn_per_run"],
                    DEFAULT_SETTINGS_POLICIES["max_attachment_size_mb"],
                    DEFAULT_SETTINGS_POLICIES["retention_days"],
                    DEFAULT_SETTINGS_POLICIES["audit_level"],
                    DEFAULT_SETTINGS_POLICIES["rate_limit_per_min"],
                ),
            )
        row = self._connection.execute(
            """
            SELECT default_model, max_turn_per_run, max_attachment_size_mb, retention_days, audit_level, rate_limit_per_min
            FROM settings_policies
            WHERE singleton_key = 'default'
            """
        ).fetchone()
        assert row is not None
        return row

    def update_policies(
        self,
        *,
        default_model: str,
        max_turn_per_run: int,
        max_attachment_size_mb: int,
        retention_days: int,
        audit_level: str,
        rate_limit_per_min: int,
    ) -> SettingsPolicy:
        """Update the singleton settings-policy row and return the new snapshot."""
        if not default_model.strip():
            raise ValueError("default_model must be non-empty")
        if max_turn_per_run < 1:
            raise ValueError("max_turn_per_run must be >= 1")
        if max_attachment_size_mb < 1:
            raise ValueError("max_attachment_size_mb must be >= 1")
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        if rate_limit_per_min < 1:
            raise ValueError("rate_limit_per_min must be >= 1")
        if audit_level not in {"off", "basic", "strict"}:
            raise ValueError("audit_level must be one of off/basic/strict")
        with self._connection:
            self._connection.execute(
                """
                UPDATE settings_policies
                SET default_model = ?,
                    max_turn_per_run = ?,
                    max_attachment_size_mb = ?,
                    retention_days = ?,
                    audit_level = ?,
                    rate_limit_per_min = ?
                WHERE singleton_key = 'default'
                """,
                (
                    default_model,
                    max_turn_per_run,
                    max_attachment_size_mb,
                    retention_days,
                    audit_level,
                    rate_limit_per_min,
                ),
            )
        return self.get_policies()


class AgentProfileVersionConflictError(ValueError):
    """Raise when agent profile optimistic locking detects a stale version."""


@dataclass(frozen=True, slots=True)
class _ConversationConfigSnapshot:
    """Frozen agent config captured when a conversation is created."""

    agent_id: str | None
    profile_version: int | None
    system_prompt: str | None


class ConversationRepository:
    """Persist and query conversations and participants."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
        """
        self._connection = connection

    def create_conversation(
        self,
        *,
        title: str,
        participant_ids: list[str],
        creator_id: str | None = None,
        caller_owner_id: str | None = None,
    ) -> Conversation:
        """Create a conversation with participant membership.

        Args:
            title: Human-readable conversation title.
            participant_ids: User IDs that belong to the conversation.
            creator_id: User ID of the creator; defaults to the first participant when omitted.
                Used for dissolve-permission checks (M234).
            caller_owner_id: The authenticated caller's owner_id. When participants span
                multiple owner scopes (e.g., human + ownerless agent), this value is used
                as the conversation owner_id so the caller can find the conversation via
                list_conversations_for_owner. Without it the old code fell back to a random
                UUID, making the conversation invisible to the creator.

        Returns:
            Created conversation entity.

        Raises:
            ValueError: When participant list is empty or references missing users.
        """
        normalized_references = list(
            dict.fromkeys(
                participant_id.strip()
                for participant_id in participant_ids
                if participant_id.strip()
            )
        )
        if not normalized_references:
            raise ValueError("participant_ids must not be empty")
        if not title.strip():
            raise ValueError("title must be non-empty")

        ordered_rows: list[sqlite3.Row] = []
        normalized_participants: list[str] = []
        for reference in normalized_references:
            resolved_user = self._resolve_participant_user_row(reference=reference)
            if resolved_user is None:
                raise ValueError("participant_ids contains unknown users")
            resolved_user_id = str(resolved_user["id"])
            if resolved_user_id in normalized_participants:
                continue
            normalized_participants.append(resolved_user_id)
            ordered_rows.append(resolved_user)
        owner_ids = {str(row["owner_id"]) for row in ordered_rows}
        conversation_id = uuid4().hex
        created_at = _utc_now()
        if caller_owner_id is not None:
            # When the authenticated caller is known, always use their owner_id so the
            # conversation is discoverable via list_conversations_for_owner, regardless of
            # whether participants span owner scopes (e.g. human + ownerless agent).
            owner_id = caller_owner_id
        elif len(owner_ids) == 1:
            owner_id = next(iter(owner_ids))
        else:
            owner_id = uuid4().hex
        conversation_type = "direct" if len(normalized_participants) == 2 else "group"
        if creator_id is None:
            resolved_creator_id = normalized_participants[0]
        else:
            creator_row = self._resolve_participant_user_row(reference=creator_id)
            if creator_row is None:
                raise ValueError("creator_id not found")
            resolved_creator_id = str(creator_row["id"])
            if resolved_creator_id not in normalized_participants:
                raise ValueError("creator_id must be one of participant_ids")
        config_snapshot = self._resolve_config_snapshot(
            participant_rows=ordered_rows,
            conversation_type=conversation_type,
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO conversations(
                    id,
                    title,
                    type,
                    owner_id,
                    creator_id,
                    is_pinned,
                    is_muted,
                    unread_count,
                    last_message_preview,
                    last_message_at,
                    config_agent_id,
                    config_profile_version,
                    config_system_prompt,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    title,
                    conversation_type,
                    owner_id,
                    resolved_creator_id,
                    0,
                    0,
                    0,
                    None,
                    None,
                    config_snapshot.agent_id,
                    config_snapshot.profile_version,
                    config_snapshot.system_prompt,
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
            creator_id=resolved_creator_id,
            is_pinned=False,
            is_muted=False,
            unread_count=0,
            last_message_preview=None,
            last_message_at=None,
            config_profile_version=config_snapshot.profile_version,
            created_at=created_at,
            participants=[self._actor_from_user_row(row) for row in ordered_rows],
        )

    def get_conversation(self, *, conversation_id: str) -> Conversation | None:
        """Load one conversation with participants."""
        row = self._connection.execute(
            """
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_profile_version, created_at
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
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_profile_version, created_at
            FROM conversations
            ORDER BY is_pinned DESC, COALESCE(last_message_at, created_at) DESC, rowid DESC
            """
        ).fetchall()
        return [self._row_to_conversation(row) for row in conversation_rows]

    def list_conversations_for_owner(self, *, owner_id: str) -> list[Conversation]:
        """Owner-scoped list — filters at the SQL layer to prevent cross-tenant leakage."""
        conversation_rows = self._connection.execute(
            """
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_profile_version, created_at
            FROM conversations
            WHERE owner_id = ?
            ORDER BY is_pinned DESC, COALESCE(last_message_at, created_at) DESC, rowid DESC
            """,
            (owner_id,),
        ).fetchall()
        return [self._row_to_conversation(row) for row in conversation_rows]

    def get_conversation_for_owner(
        self, *, conversation_id: str, owner_id: str
    ) -> Conversation | None:
        """Return the conversation only when it is owned by ``owner_id``; else None.

        Notes:
            Returning None (not raising) lets API routes translate the absence to a
            404 without leaking whether the resource exists under a different owner.
        """
        conversation = self.get_conversation(conversation_id=conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            return None
        return conversation

    def delete_conversation(self, *, conversation_id: str, requester_id: str) -> None:
        """Dissolve a conversation and cascade-delete all messages and participants.

        Only the creator of the conversation may call this method.

        Args:
            conversation_id: Identifier of the conversation to delete.
            requester_id: User ID of the caller; must match the stored creator_id.

        Raises:
            ValueError: When the conversation does not exist.
            PermissionError: When the requester is not the conversation creator.

        Side Effects:
            Deletes the conversation row; ON DELETE CASCADE removes messages,
            conversation_participants, conversation_events, and relay_tasks.
        """
        row = self._connection.execute(
            "SELECT creator_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("conversation_id not found")
        # Permission check is enforced here in the service layer, not only in the UI.
        if str(row["creator_id"]) != requester_id:
            raise PermissionError(
                "only the conversation creator can dissolve this conversation"
            )
        with self._connection:
            self._connection.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )

    def add_participants(
        self, *, conversation_id: str, references: list[str]
    ) -> Conversation:
        """Add participants to an existing conversation; return the new snapshot.

        Reuses the create path's reference resolution (``agent:<id>`` → user row)
        and membership INSERT. Idempotent: references already in the conversation
        are skipped. Per decision 3 this only writes membership rows — it does not
        recompute or refreeze ``config_profile_version`` (the conversation keeps
        the version frozen at create time).

        Raises:
            ValueError: When the reference list is empty, the conversation does
                not exist, or a reference resolves to no known user.
        """
        normalized_references = list(
            dict.fromkeys(
                reference.strip() for reference in references if reference.strip()
            )
        )
        if not normalized_references:
            raise ValueError("participants must not be empty")
        convo_row = self._connection.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if convo_row is None:
            raise ValueError("conversation_id not found")
        existing_user_ids = {
            str(row["user_id"])
            for row in self._connection.execute(
                "SELECT user_id FROM conversation_participants WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchall()
        }
        to_insert: list[str] = []
        for reference in normalized_references:
            resolved_user = self._resolve_participant_user_row(reference=reference)
            if resolved_user is None:
                raise ValueError("participants contains unknown users")
            resolved_user_id = str(resolved_user["id"])
            if resolved_user_id in existing_user_ids:
                continue
            existing_user_ids.add(resolved_user_id)
            to_insert.append(resolved_user_id)
        if to_insert:
            with self._connection:
                self._connection.executemany(
                    "INSERT INTO conversation_participants(conversation_id, user_id) VALUES (?, ?)",
                    [(conversation_id, user_id) for user_id in to_insert],
                )
        updated = self.get_conversation(conversation_id=conversation_id)
        assert updated is not None
        return updated

    def remove_participant(self, *, conversation_id: str, user_id: str) -> None:
        """Remove one participant from a conversation (leave-group operation).

        Args:
            conversation_id: Identifier of the target conversation.
            user_id: Identifier of the user leaving the conversation.

        Raises:
            ValueError: When the conversation does not exist or user is not a participant.
        """
        convo_row = self._connection.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if convo_row is None:
            raise ValueError("conversation_id not found")
        participant_row = self._connection.execute(
            "SELECT 1 FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if participant_row is None:
            raise ValueError("user_id not a participant of this conversation")
        with self._connection:
            self._connection.execute(
                "DELETE FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
                (conversation_id, user_id),
            )

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert one conversation row into a domain model with participants."""
        participant_rows = self._connection.execute(
            """
            SELECT users.id, users.username, users.display_name,
                   COALESCE(ap.is_stale, 0) AS is_stale
            FROM conversation_participants
            JOIN users ON users.id = conversation_participants.user_id
            LEFT JOIN agent_profiles ap
                   ON ap.agent_id = SUBSTR(users.username, LENGTH('agent:') + 1)
                  AND users.username LIKE 'agent:%'
            WHERE conversation_participants.conversation_id = ?
            ORDER BY conversation_participants.rowid
            """,
            (row["id"],),
        ).fetchall()
        profile_version = (
            row["config_profile_version"]
            if "config_profile_version" in row.keys()
            else None
        )
        row_keys = row.keys()
        # creator_id was added by M234 migration; fall back to owner_id for legacy rows.
        creator_id = (
            str(row["creator_id"]) if "creator_id" in row_keys else str(row["owner_id"])
        )
        return Conversation(
            id=row["id"],
            title=row["title"],
            participant_ids=[str(item["id"]) for item in participant_rows],
            type=row["type"],
            owner_id=row["owner_id"],
            creator_id=creator_id,
            is_pinned=bool(row["is_pinned"]),
            is_muted=bool(row["is_muted"]),
            unread_count=int(row["unread_count"]),
            last_message_preview=row["last_message_preview"]
            if "last_message_preview" in row_keys
            else None,
            last_message_at=row["last_message_at"],
            config_profile_version=profile_version,
            created_at=row["created_at"],
            participants=[self._actor_from_user_row(item) for item in participant_rows],
        )

    def _resolve_participant_user_row(self, *, reference: str) -> sqlite3.Row | None:
        """Resolve one participant reference into a concrete IM user row."""
        normalized = reference.strip()
        if not normalized:
            return None
        if normalized.startswith("user:"):
            user_id = normalized[len("user:") :].strip()
            if not user_id:
                return None
            return self._connection.execute(
                "SELECT id, username, display_name, owner_id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if normalized.startswith("agent:"):
            agent_id = normalized[len("agent:") :].strip()
            if not agent_id:
                return None
            return self._connection.execute(
                "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
                (f"agent:{agent_id}",),
            ).fetchone()

        by_id = self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE id = ?",
            (normalized,),
        ).fetchone()
        if by_id is not None:
            return by_id
        by_agent_username = self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
            (f"agent:{normalized}",),
        ).fetchone()
        if by_agent_username is not None:
            return by_agent_username
        return self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
            (normalized,),
        ).fetchone()

    @staticmethod
    def _actor_from_user_row(row: sqlite3.Row) -> Actor:
        """Convert one IM user row to actor-first identity."""
        user_id = str(row["id"])
        username = str(row["username"])
        display_name = (
            str(row["display_name"]) if row["display_name"] is not None else None
        )
        keys = row.keys()
        if username.startswith("agent:"):
            agent_id = username[len("agent:") :].strip() or user_id
            is_stale = bool(row["is_stale"]) if "is_stale" in keys else None
            return Actor(
                type="agent",
                id=agent_id,
                display_name=display_name,
                user_id=user_id,
                is_stale=is_stale,
            )
        return Actor(
            type="user", id=user_id, display_name=display_name, user_id=user_id
        )

    def _resolve_config_profile_version(
        self, *, owner_id: str, participant_ids: list[str]
    ) -> int | None:
        """Return the frozen profile version that a new conversation should bind to."""
        if not participant_ids:
            return None
        participant_rows: list[sqlite3.Row] = []
        seen_user_ids: set[str] = set()
        for reference in participant_ids:
            resolved = self._resolve_participant_user_row(reference=reference)
            if resolved is None:
                continue
            resolved_user_id = str(resolved["id"])
            if resolved_user_id in seen_user_ids:
                continue
            participant_rows.append(resolved)
            seen_user_ids.add(resolved_user_id)
        if not participant_rows:
            return None
        snapshot = self._resolve_config_snapshot(
            participant_rows=participant_rows, conversation_type="group"
        )
        return snapshot.profile_version

    def _resolve_config_snapshot(
        self,
        *,
        participant_rows: list[sqlite3.Row],
        conversation_type: str,
    ) -> _ConversationConfigSnapshot:
        """Freeze the agent config snapshot that should back a new conversation."""
        for row in participant_rows:
            snapshot = self._profile_snapshot_for_participant(row=row)
            if snapshot is None:
                continue
            if conversation_type == "direct":
                return snapshot
            return _ConversationConfigSnapshot(
                agent_id=None,
                profile_version=snapshot.profile_version,
                system_prompt=None,
            )
        return _ConversationConfigSnapshot(
            agent_id=None, profile_version=None, system_prompt=None
        )

    def _profile_snapshot_for_participant(
        self, *, row: sqlite3.Row
    ) -> _ConversationConfigSnapshot | None:
        """Resolve one participant row into an agent profile snapshot when it represents an agent."""
        candidate_agent_ids: list[str] = [str(row["id"])]
        username = str(row["username"])
        if username.startswith("agent:"):
            alias_agent_id = username[len("agent:") :].strip()
            if alias_agent_id:
                candidate_agent_ids.append(alias_agent_id)
        for candidate_agent_id in candidate_agent_ids:
            profile_row = self._connection.execute(
                "SELECT agent_id, profile_version, system_prompt FROM agent_profiles WHERE agent_id = ?",
                (candidate_agent_id,),
            ).fetchone()
            if profile_row is None:
                continue
            return _ConversationConfigSnapshot(
                agent_id=str(profile_row["agent_id"]),
                profile_version=int(profile_row["profile_version"]),
                system_prompt=str(profile_row["system_prompt"]),
            )
        return None


class MessageRepository:
    """Persist and query conversation messages."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        notify: Callable[[ConversationEvent], None] | None = None,
    ) -> None:
        """Bind repository to a database connection.

        Args:
            connection: SQLite connection used for reads and writes.
            notify: 可选；消息相关事件在事务提交后广播（与 EventRepository 独立写路径）。
        """
        self._connection = connection
        self._notify = notify

    def create_message(
        self,
        *,
        conversation_id: str,
        sender_user_id: str,
        content: str,
        sender_type: str = "user",
        attachments: list[Attachment] | None = None,
        auto_complete_delivery: bool = True,
        tool_calls: list[ToolCall] | None = None,
        token_usage: TokenUsage | None = None,
        allow_empty: bool = False,
        kernel_message_id: str | None = None,
    ) -> Message:
        """Create a message in a conversation.

        Args:
            conversation_id: Target conversation identifier.
            sender_user_id: Sender user identifier.
            content: Plain text body of the message.
            sender_type: Sender kind; must be user, agent, or system.
            attachments: Attachment descriptors stored alongside the message.
            auto_complete_delivery: When True, local-only writes synchronously close delivery to completed
                and persist both message.sent and message.delivered. Relay-backed writes pass False so
                gateway receipts remain the single source of truth for completion.

        Returns:
            Created message entity.

        Raises:
            ValueError: When conversation/sender is missing, owner scope mismatches, sender type is invalid,
                or sender is not a participant for user-originated messages.
        """
        normalized_attachments = _normalize_attachments(attachments)
        # feat-340-M2: agent-runtime messages start empty and stream content via update_runtime_state;
        # callers opt in with allow_empty so we don't break the user-message invariant.
        if not allow_empty and not content.strip() and not normalized_attachments:
            raise ValueError("message must include content or attachments")
        if sender_type not in {"user", "agent", "system"}:
            raise ValueError("sender_type must be one of: user, agent, system")
        conversation_exists = self._connection.execute(
            "SELECT owner_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conversation_exists is None:
            raise ValueError("conversation_id not found")

        sender_user = self._resolve_sender_user_row(
            sender_user_id=sender_user_id,
            sender_type=sender_type,
        )
        if sender_user is None:
            raise ValueError("sender_user_id not found")
        resolved_sender_user_id = str(sender_user["id"])
        sender_actor = self._actor_from_sender_row(
            sender_type=sender_type,
            sender_user_id=resolved_sender_user_id,
            sender_username=str(sender_user["username"]),
            sender_display_name=str(sender_user["display_name"])
            if sender_user["display_name"] is not None
            else None,
        )
        participant_exists = self._connection.execute(
            """
            SELECT 1
            FROM conversation_participants
            WHERE conversation_id = ? AND user_id = ?
            """,
            (conversation_id, resolved_sender_user_id),
        ).fetchone()
        # System messages are server-originated and bypass the owner scope check;
        # they can be injected into any conversation regardless of participant/owner alignment.
        if sender_type != "system":
            if participant_exists is None and str(sender_user["owner_id"]) != str(
                conversation_exists["owner_id"]
            ):
                raise ValueError("sender_user_id is outside conversation owner scope")

        if sender_type == "user" and participant_exists is None:
            raise ValueError("sender_user_id is not a participant of conversation")

        message_id = uuid4().hex
        created_at = _utc_now()
        initial_status = "sent"
        final_status = "completed" if auto_complete_delivery else initial_status
        attachments_json = _encode_attachments(normalized_attachments)
        event_attachments = [
            _attachment_to_dict(item) for item in normalized_attachments
        ]
        sent_payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "sender_user_id": resolved_sender_user_id,
            "sender_type": sender_type,
            "sender": {"type": sender_actor.type, "id": sender_actor.id},
            "attachments": event_attachments,
            "progress_state": "pending",
            "semantic": "persisted_to_im",
        }
        pending_live_events: list[ConversationEvent] = []
        normalized_tool_calls = _normalize_tool_calls(tool_calls)
        tool_calls_json = (
            _encode_tool_calls(normalized_tool_calls)
            if normalized_tool_calls is not None
            else None
        )
        token_usage_json = _encode_token_usage(token_usage)
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
                    created_at,
                    tool_calls_json,
                    token_usage_json,
                    kernel_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    resolved_sender_user_id,
                    sender_type,
                    content,
                    attachments_json,
                    initial_status,
                    created_at,
                    tool_calls_json,
                    token_usage_json,
                    kernel_message_id,
                ),
            )
            pending_live_events.append(
                self._insert_event(
                    conversation_id=conversation_id,
                    message_id=message_id,
                    event_type="message.sent",
                    delivery_status=initial_status,
                    payload=sent_payload,
                )
            )
            if auto_complete_delivery:
                pending_live_events.append(
                    self._insert_event(
                        conversation_id=conversation_id,
                        message_id=message_id,
                        event_type="message.delivered",
                        delivery_status="completed",
                        payload={
                            **sent_payload,
                            "progress_state": "completed",
                            "semantic": "message_history_ready",
                        },
                    )
                )
                self._connection.execute(
                    "UPDATE messages SET delivery_status = ? WHERE id = ?",
                    (final_status, message_id),
                )
            # Only increment unread_count for messages from other participants, not the conversation owner's own messages.
            owner_id = str(conversation_exists["owner_id"])
            is_own_message = resolved_sender_user_id == owner_id
            if is_own_message:
                self._connection.execute(
                    "UPDATE conversations SET last_message_preview = ?, last_message_at = ? WHERE id = ?",
                    (
                        _to_message_preview(
                            content=content, attachments=normalized_attachments
                        ),
                        created_at,
                        conversation_id,
                    ),
                )
            else:
                self._connection.execute(
                    "UPDATE conversations SET last_message_preview = ?, last_message_at = ?, unread_count = unread_count + 1 WHERE id = ?",
                    (
                        _to_message_preview(
                            content=content, attachments=normalized_attachments
                        ),
                        created_at,
                        conversation_id,
                    ),
                )
        if self._notify is not None:
            for live_event in pending_live_events:
                self._notify(live_event)
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            sender_user_id=resolved_sender_user_id,
            sender_type=sender_type,
            sender=sender_actor,
            content=content,
            attachments=normalized_attachments,
            delivery_status=final_status,
            created_at=created_at,
            tool_calls=normalized_tool_calls,
            token_usage=token_usage,
            # feat-414: 建行时始终为 None，由 on_message_completed 写入。
            elapsed_ms=None,
            kernel_message_id=kernel_message_id,
        )

    def update_runtime_state(
        self,
        *,
        message_id: str,
        content_append: str | None = None,
        content_replace: str | None = None,
        tool_calls_upsert: list[ToolCall] | None = None,
        token_usage: TokenUsage | None = None,
        delivery_status: str | None = None,
        elapsed_ms: int | None = None,
        kernel_message_id: str | None = None,
    ) -> Message:
        """Apply one runtime-stream patch to an agent message.

        Designed for feat-340-M2 event bridge: kernel emits incremental deltas which
        we accumulate into the persisted message row, so that ``list_messages`` can
        reconstruct the final agent reply (text + tool calls + token usage) on reload
        without replaying every event.

        Args:
            message_id: Target message identifier.
            content_append: When provided, concatenated onto current message content.
                Mutually exclusive with ``content_replace``.
            content_replace: When provided, overwrites current message content.
            tool_calls_upsert: Tool calls to upsert by ``id`` into ``tool_calls_json``.
                New ids append; existing ids replace in place to preserve display order.
            token_usage: When provided, overwrites ``token_usage_json``.
            delivery_status: When provided, updates ``delivery_status`` column.
            elapsed_ms: feat-414 — 本轮墙钟耗时（毫秒）。非 None 时写入列；None（默认）时
                使用 Sentinel 机制跳过（同 token_usage），不清掉已有值。

        Returns:
            Refreshed Message entity reflecting the patch.

        Raises:
            ValueError: When ``message_id`` does not exist or arguments conflict.
        """
        if content_append is not None and content_replace is not None:
            raise ValueError(
                "content_append and content_replace are mutually exclusive"
            )
        row = self._connection.execute(
            "SELECT content, tool_calls_json, thinking_json, token_usage_json, conversation_id FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"message_id not found: {message_id}")

        next_content: str | None = None
        if content_replace is not None:
            next_content = content_replace
        elif content_append is not None:
            next_content = (
                str(row["content"]) if row["content"] is not None else ""
            ) + content_append

        next_tool_calls_json: str | None | object = _UNSET
        if tool_calls_upsert is not None:
            existing = _decode_tool_calls(row["tool_calls_json"]) or []
            existing_thinking = (
                _decode_thinking(row["thinking_json"])
                if "thinking_json" in row.keys()
                else None
            ) or []
            existing_by_id = {tc.id: tc for tc in existing}
            order: list[str] = [tc.id for tc in existing]
            for upsert in _normalize_tool_calls(tool_calls_upsert) or []:
                if upsert.id not in existing_by_id:
                    # feat-439-M2: new tool id → assign the shared process-timeline seq
                    # (max over current thinking + tools, +1) so thinking/tools share one
                    # monotonic arrival order. A later same-id upsert (completed) keeps it.
                    order.append(upsert.id)
                    seq = _next_process_seq(
                        existing_thinking, list(existing_by_id.values())
                    )
                    existing_by_id[upsert.id] = replace(upsert, seq=seq)
                else:
                    # Preserve the seq assigned at first upsert; the gateway never sends
                    # seq (IM owns assignment), so a None on the incoming completed frame
                    # must not wipe it.
                    prior_seq = existing_by_id[upsert.id].seq
                    existing_by_id[upsert.id] = replace(
                        upsert, seq=upsert.seq if upsert.seq is not None else prior_seq
                    )
            merged = [existing_by_id[tcid] for tcid in order]
            next_tool_calls_json = _encode_tool_calls(merged)

        next_token_usage_json: str | None | object = _UNSET
        if token_usage is not None:
            next_token_usage_json = _encode_token_usage(token_usage)

        sets: list[str] = []
        values: list[object] = []
        if next_content is not None:
            sets.append("content = ?")
            values.append(next_content)
        if next_tool_calls_json is not _UNSET:
            sets.append("tool_calls_json = ?")
            values.append(next_tool_calls_json)
        if next_token_usage_json is not _UNSET:
            sets.append("token_usage_json = ?")
            values.append(next_token_usage_json)
        # feat-414: Sentinel 同 token_usage — None 表示"不改"，有值则写入。
        if elapsed_ms is not None:
            sets.append("elapsed_ms = ?")
            values.append(elapsed_ms)
        if delivery_status is not None:
            sets.append("delivery_status = ?")
            values.append(delivery_status)
        # feat-445-M1: relay 收尾把该气泡的 kernel message_id 落库。None（默认）= 不改，
        # 不清掉已写入值（同 token_usage/elapsed_ms 的 sentinel 语义）。
        if kernel_message_id is not None:
            sets.append("kernel_message_id = ?")
            values.append(kernel_message_id)
        if not sets:
            raise ValueError(
                "update_runtime_state requires at least one field to change"
            )
        values.append(message_id)
        with self._connection:
            self._connection.execute(
                f"UPDATE messages SET {', '.join(sets)} WHERE id = ?",
                tuple(values),
            )
        refreshed = self._connection.execute(
            """
            SELECT
                messages.id,
                messages.conversation_id,
                messages.sender_user_id,
                messages.sender_type,
                messages.content,
                messages.attachments_json,
                messages.delivery_status,
                messages.created_at,
                messages.tool_calls_json,
                messages.thinking_json,
                messages.token_usage_json,
                messages.elapsed_ms,
                messages.permission_request_json,
                messages.kernel_message_id,
                users.username AS sender_username,
                users.display_name AS sender_display_name
            FROM messages
            LEFT JOIN users ON users.id = messages.sender_user_id
            WHERE messages.id = ?
            """,
            (message_id,),
        ).fetchone()
        return self._message_from_row(refreshed)

    def append_thinking_segment(self, *, message_id: str, text: str) -> Message:
        """feat-439-M2: 追加一段思考到 ``messages.thinking_json``，返回刷新后的消息。

        ``seq`` 在此（持久化边界）统一赋予：思考与工具**共享一个 per-message 单调递增
        计数器**（= 当前所有过程项 seq 的 max + 1），按真实到达序赋值且全局唯一。这样
        渲染端按 seq 把思考与工具 merge 成一条时间线，且唯一 seq 让 live WS 事件可幂等
        去重（重放/双投递不重复）。live 与历史回放都读同一持久化值，口径一致。
        """
        # code-review fix: 计 seq 的 SELECT 与写入的 UPDATE 必须在同一事务内（对齐
        # update_runtime_state 写法），避免并发/崩溃下读到旧 seq 后半写导致序号错乱。
        with self._connection:
            row = self._connection.execute(
                "SELECT tool_calls_json, thinking_json FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"message_id not found: {message_id}")
            existing_tools = _decode_tool_calls(row["tool_calls_json"]) or []
            existing = _decode_thinking(row["thinking_json"]) or []
            seq = _next_process_seq(existing, existing_tools)
            existing.append(ThinkingSegment(seq=seq, text=text))
            self._connection.execute(
                "UPDATE messages SET thinking_json = ? WHERE id = ?",
                (_encode_thinking(existing), message_id),
            )
        refreshed = self._connection.execute(
            """
            SELECT
                messages.id,
                messages.conversation_id,
                messages.sender_user_id,
                messages.sender_type,
                messages.content,
                messages.attachments_json,
                messages.delivery_status,
                messages.created_at,
                messages.tool_calls_json,
                messages.thinking_json,
                messages.token_usage_json,
                messages.elapsed_ms,
                messages.permission_request_json,
                messages.kernel_message_id,
                users.username AS sender_username,
                users.display_name AS sender_display_name
            FROM messages
            LEFT JOIN users ON users.id = messages.sender_user_id
            WHERE messages.id = ?
            """,
            (message_id,),
        ).fetchone()
        return self._message_from_row(refreshed)

    def get_conversation_id(self, *, message_id: str) -> str | None:
        """Return a message's conversation_id without mutating the row (bugfix-417-M3).

        Used by the run_heartbeat liveness path, which must append a conversation_events
        row but must NOT patch the message (content / tool_calls / delivery_status).
        Returns ``None`` for an unknown message id.
        """
        row = self._connection.execute(
            "SELECT conversation_id FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row["conversation_id"])

    def list_messages(
        self,
        *,
        conversation_id: str,
        limit: int = 50,
        before_message_id: str | None = None,
        mark_as_read: bool = False,
    ) -> list[Message]:
        """List messages for a conversation in insertion order.

        Args:
            conversation_id: Target conversation identifier.
            limit: Maximum number of recent messages to return.
            before_message_id: Exclusive cursor; return messages older than this message.
            mark_as_read: Whether to clear unread_count for the conversation after loading latest page.

        Returns:
            Messages ordered from oldest to newest within the selected page.
        """
        bounded_limit = max(1, min(limit, 200))
        merged_messages = self._list_message_timeline(conversation_id=conversation_id)
        if before_message_id is not None:
            cursor_index = next(
                (
                    index
                    for index, message in enumerate(merged_messages)
                    if message.id == before_message_id
                ),
                None,
            )
            if cursor_index is None:
                raise ValueError("before_message_id not found")
            merged_messages = merged_messages[:cursor_index]
        paged_messages = merged_messages[-bounded_limit:]
        if mark_as_read and before_message_id is None:
            with self._connection:
                self._connection.execute(
                    "UPDATE conversations SET unread_count = 0 WHERE id = ?",
                    (conversation_id,),
                )
        return paged_messages

    def _list_message_timeline(self, *, conversation_id: str) -> list[Message]:
        """Return persisted messages merged with visible relay-history messages."""
        message_rows = self._connection.execute(
            """
            SELECT
                messages.id,
                messages.conversation_id,
                messages.sender_user_id,
                messages.sender_type,
                messages.content,
                messages.attachments_json,
                messages.delivery_status,
                messages.created_at,
                messages.tool_calls_json,
                messages.thinking_json,
                messages.token_usage_json,
                messages.elapsed_ms,
                messages.permission_request_json,
                messages.kernel_message_id,
                users.username AS sender_username,
                users.display_name AS sender_display_name
            FROM messages
            LEFT JOIN users ON users.id = messages.sender_user_id
            WHERE conversation_id = ?
            ORDER BY messages.rowid
            """,
            (conversation_id,),
        ).fetchall()
        merged = [self._message_from_row(row) for row in message_rows]
        # M17/R8-1: once a turn produces a real agent message (M16 streaming chain),
        # the relay.completed mirror becomes a duplicate. Suppress synthetic rows
        # whenever the conversation already has any real agent-typed message —
        # keeps legacy threads that only have relay events intact (no real agent
        # row → still synthesise from events).
        has_real_agent_message = any(m.sender_type == "agent" for m in merged)
        event_rows = self._connection.execute(
            """
            SELECT event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at
            FROM conversation_events
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        for row in event_rows:
            synthetic_message = self._message_from_visible_event_row(row)
            if synthetic_message is None:
                continue
            if has_real_agent_message and ":relay:" in synthetic_message.id:
                continue
            merged = _upsert_message(merged, synthetic_message)
        return merged

    def append_permission_request(
        self,
        *,
        message_id: str,
        permission_data: dict[str, object],
    ) -> str:
        """Append one permission_request dict to the message's list, dedup by request_id.

        bugfix-367: 同一 message 上多次 ask 不再相互覆盖。同 request_id 的二次写入
        视为 idempotent 替换(网络重传等);新 request_id 追加到 list 尾,以便 UI
        按时间顺序渲染历史小条 + 当前 pending 卡。

        Args:
            message_id: Target message; must exist.
            permission_data: Full permission request dict to append/replace. Caller
                supplies ``status="pending"`` (and ``request_id``).

        Returns:
            The conversation_id of the target message (needed by the bridge).

        Raises:
            ValueError: When ``message_id`` does not exist or ``permission_data``
                lacks ``request_id``.
        """
        request_id = permission_data.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("permission_data must include a non-empty request_id")

        row = self._connection.execute(
            "SELECT conversation_id, permission_request_json FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"message_id not found: {message_id}")
        existing = _load_permission_requests(row["permission_request_json"])
        replaced = False
        for index, entry in enumerate(existing):
            if entry.get("request_id") == request_id:
                existing[index] = dict(permission_data)
                replaced = True
                break
        if not replaced:
            existing.append(dict(permission_data))
        # bugfix-410-M2 (#98): stamp the awaiting_permission liveness marker so the
        # relay watchdog exempts this running message from the 120s idle reap while
        # the user decides. The Gateway heartbeat refreshes it; resolution clears it.
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET permission_request_json = ?, awaiting_permission_at = ? WHERE id = ?",
                (json.dumps(existing), _utc_now(), message_id),
            )
        return str(row["conversation_id"])

    def update_permission_resolution(
        self,
        *,
        message_id: str,
        request_id: str,
        decision: str,
    ) -> str:
        """Mark one specific permission_request entry as resolved within the list.

        bugfix-367: list 化后 resolved 写入必须按 request_id 定位 —— 不再覆盖整列
        (那会丢掉同泡内其他历史 ask)。未匹配到 request_id 时 raise,防止前端
        reducer 状态机被静默放空。

        Args:
            message_id: Target message; must exist.
            request_id: Stable identifier matching a pending request.
            decision: User-chosen option id (e.g. ``"allow_once"``, ``"deny"``).

        Returns:
            The conversation_id of the target message.

        Raises:
            ValueError: When ``message_id`` does not exist or ``request_id`` is not
                found in the message's permission_requests list.
        """
        row = self._connection.execute(
            "SELECT conversation_id, permission_request_json FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"message_id not found: {message_id}")
        existing = _load_permission_requests(row["permission_request_json"])
        target_index: int | None = None
        for index, entry in enumerate(existing):
            if entry.get("request_id") == request_id:
                target_index = index
                break
        if target_index is None:
            raise ValueError(
                f"request_id {request_id!r} not found in permission_requests of message {message_id}"
            )
        existing[target_index] = {
            **existing[target_index],
            "status": "resolved",
            "decision": decision,
        }
        # bugfix-410-M2 (#98): clear the awaiting_permission marker only when no other
        # ask on this message is still pending (a message can carry several asks).
        # While any remains pending the marker stays set (and heartbeat-refreshed).
        any_still_pending = any(entry.get("status") == "pending" for entry in existing)
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET permission_request_json = ?, "
                "awaiting_permission_at = CASE WHEN ? THEN awaiting_permission_at ELSE NULL END "
                "WHERE id = ?",
                (json.dumps(existing), 1 if any_still_pending else 0, message_id),
            )
        return str(row["conversation_id"])

    def clear_awaiting_permission_marker(self, *, message_id: str) -> None:
        """Drop the awaiting_permission marker (bugfix-410-M2 #98).

        Called when a run reaches a terminal state (failed/cancelled/completed)
        so a marker left set by a never-resolved ask cannot keep exempting the
        message after the run is already over.
        """
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET awaiting_permission_at = NULL WHERE id = ?",
                (message_id,),
            )

    def refresh_awaiting_permission_markers(self, *, agent_ids: list[str]) -> int:
        """Touch awaiting_permission_at for the given agents' still-running, still-
        marked messages (bugfix-410-M2 #98).

        Invoked from the owning node's heartbeat handler: while the Gateway is
        alive it keeps refreshing the marker timestamp, so the relay watchdog's
        crash-threshold check treats the wait as live and never reaps it. A
        Gateway crash stops the heartbeat → the marker goes stale → the message
        is reaped normally. Only refreshes rows already marked (never sets a new
        marker), so it cannot resurrect a resolved/terminal message.

        Agents are stored as users with ``username = 'agent:<agent_id>'``; we
        resolve via that join so callers pass the same agent_ids the heartbeat
        node owns.

        Returns:
            Number of marker timestamps refreshed.
        """
        if not agent_ids:
            return 0
        usernames = [f"agent:{agent_id}" for agent_id in agent_ids]
        placeholders = ",".join("?" for _ in usernames)
        with self._connection:
            cursor = self._connection.execute(
                f"UPDATE messages SET awaiting_permission_at = ? "
                f"WHERE delivery_status = 'running' "
                f"AND awaiting_permission_at IS NOT NULL "
                f"AND sender_user_id IN ("
                f"  SELECT id FROM users WHERE username IN ({placeholders})"
                f")",
                (_utc_now(), *usernames),
            )
        return cursor.rowcount if cursor.rowcount is not None else 0

    def _message_from_row(self, row: sqlite3.Row) -> Message:
        """Convert one stored SQLite row into a Message domain model."""
        tool_calls_value = (
            row["tool_calls_json"] if "tool_calls_json" in row.keys() else None
        )
        thinking_value = row["thinking_json"] if "thinking_json" in row.keys() else None
        token_usage_value = (
            row["token_usage_json"] if "token_usage_json" in row.keys() else None
        )
        permission_request_value = (
            row["permission_request_json"]
            if "permission_request_json" in row.keys()
            else None
        )
        # feat-414: 旧行无此列时（key 不在 row.keys()）回落 None，不报 KeyError。
        elapsed_ms_value: int | None = (
            row["elapsed_ms"] if "elapsed_ms" in row.keys() else None
        )
        # feat-445-M1: 旧行 / 非来自含该列 SELECT 的 row 回落 None，不报 KeyError。
        kernel_message_id_value: str | None = (
            row["kernel_message_id"] if "kernel_message_id" in row.keys() else None
        )
        permission_requests = _load_permission_requests(permission_request_value)
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            sender_user_id=row["sender_user_id"],
            sender_type=row["sender_type"],
            sender=self._actor_from_sender_row(
                sender_type=str(row["sender_type"]),
                sender_user_id=str(row["sender_user_id"]),
                sender_username=str(row["sender_username"])
                if row["sender_username"] is not None
                else None,
                sender_display_name=(
                    str(row["sender_display_name"])
                    if row["sender_display_name"] is not None
                    else None
                ),
            ),
            content=row["content"],
            attachments=_decode_attachments(row["attachments_json"]),
            delivery_status=row["delivery_status"],
            created_at=row["created_at"],
            tool_calls=_decode_tool_calls(tool_calls_value),
            thinking=_decode_thinking(thinking_value),
            token_usage=_decode_token_usage(token_usage_value),
            elapsed_ms=elapsed_ms_value,
            permission_requests=permission_requests,
            kernel_message_id=kernel_message_id_value,
        )

    def _message_from_visible_event_row(self, row: sqlite3.Row) -> Message | None:
        """Convert one relay-visible event row into the synthetic message shown in history."""
        event_type = str(row["event_type"])
        if event_type not in {"relay.completed", "relay.failed"}:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        # bugfix-365: when the real `messages` row for this event is already an
        # agent row in a terminal state (failed/completed), the synthetic mirror
        # would just paint a second bubble for the same logical message — the
        # watchdog path is the canonical case (writes `relay.failed` after flipping
        # the real row to `failed`). Suppress the synthetic; the real row carries
        # the detail text via the watchdog's content backfill in `relay_watchdog`.
        # Scoping to `sender_type='agent'` preserves the legacy pattern where one
        # *user* message_id fans out into multiple synthetic agent reply rows.
        real_message_id = _optional_text(payload.get("message_id"))
        if real_message_id is not None:
            real_row = self._connection.execute(
                "SELECT delivery_status, sender_type FROM messages WHERE id = ?",
                (real_message_id,),
            ).fetchone()
            if (
                real_row is not None
                and str(real_row["sender_type"]) == "agent"
                and str(real_row["delivery_status"]) in {"failed", "completed"}
            ):
                return None
        synthetic_message_id = _synthetic_message_id_from_event_payload(payload)
        if synthetic_message_id is None:
            return None
        content = _visible_content_from_event(event_type=event_type, payload=payload)
        if content is None:
            return None
        sender = self._actor_from_event_payload(payload)
        sender_user_id = sender.user_id or sender.id
        delivery_status = (
            "running"
            if event_type == "relay.processing"
            else "failed"
            if event_type == "relay.failed"
            else "completed"
        )
        return Message(
            id=synthetic_message_id,
            conversation_id=str(row["conversation_id"]),
            sender_user_id=sender_user_id,
            sender_type="agent",
            sender=sender,
            content=content,
            attachments=[],
            delivery_status=delivery_status,
            created_at=str(row["created_at"]),
        )

    def _actor_from_event_payload(self, payload: dict[str, object]) -> Actor:
        """Build the agent actor identity exposed for synthetic relay history rows."""
        agent_id = _optional_text(payload.get("agent_id"))
        sender_display_name = (
            _optional_text(payload.get("sender_display_name"))
            or _optional_text(payload.get("display_name"))
            or _optional_text(payload.get("agent_display_name"))
        )
        if agent_id is not None:
            sender_row = self._connection.execute(
                "SELECT id, display_name FROM users WHERE username = ?",
                (f"agent:{agent_id}",),
            ).fetchone()
            return Actor(
                type="agent",
                id=agent_id,
                display_name=sender_display_name
                or (
                    str(sender_row["display_name"]) if sender_row is not None else None
                ),
                user_id=str(sender_row["id"])
                if sender_row is not None
                else f"agent:{agent_id}",
            )
        fallback_display_name = sender_display_name or "Agent"
        return Actor(
            type="agent",
            id=fallback_display_name,
            display_name=sender_display_name,
            user_id=f"agent:{fallback_display_name}",
        )

    def _resolve_sender_user_row(
        self, *, sender_user_id: str, sender_type: str
    ) -> sqlite3.Row | None:
        """Resolve sender identity by stable actor id to concrete IM user row."""
        normalized_sender = sender_user_id.strip()
        if not normalized_sender:
            return None
        if normalized_sender.startswith("user:"):
            normalized_sender = normalized_sender[len("user:") :].strip()
            if not normalized_sender:
                return None
        if sender_type == "agent" and normalized_sender.startswith("agent:"):
            normalized_sender = normalized_sender[len("agent:") :].strip()
            if not normalized_sender:
                return None

        by_id = self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE id = ?",
            (normalized_sender,),
        ).fetchone()
        if by_id is not None:
            return by_id
        if sender_type == "agent":
            return self._connection.execute(
                "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
                (f"agent:{normalized_sender}",),
            ).fetchone()
        return self._connection.execute(
            "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
            (normalized_sender,),
        ).fetchone()

    @staticmethod
    def _actor_from_sender_row(
        *,
        sender_type: str,
        sender_user_id: str,
        sender_username: str | None,
        sender_display_name: str | None,
    ) -> Actor:
        """Build actor-first sender identity from message row and user metadata."""
        if (
            sender_type == "agent"
            and sender_username is not None
            and sender_username.startswith("agent:")
        ):
            actor_id = sender_username[len("agent:") :].strip() or sender_user_id
            return Actor(
                type="agent",
                id=actor_id,
                display_name=sender_display_name,
                user_id=sender_user_id,
            )
        return Actor(
            type=sender_type,
            id=sender_user_id,
            display_name=sender_display_name,
            user_id=sender_user_id,
        )

    def _insert_event(
        self,
        *,
        conversation_id: str,
        message_id: str | None,
        event_type: str,
        delivery_status: str,
        payload: dict[str, object],
    ) -> ConversationEvent:
        """在现有事务内插入一条 conversation_events 并返回完整实体。"""
        created_at = _utc_now()
        payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
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


class AgentProfileRepository:
    """Persist and query agent configuration profiles."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_profiles(self) -> list[AgentProfile]:
        """List agent profiles in stable creation order."""
        rows = self._connection.execute(
            """
            SELECT agent_id, owner_id, node_id, display_name, description, system_prompt, skills_json,
                   tool_allowlist_json, group_reply_policy, default_model, workspace_root, profile_version,
                   is_stale, features_json, custom_prompt, heartbeat_json
            FROM agent_profiles
            ORDER BY created_at, rowid
            """
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def list_runtime_selectable_profiles(self) -> list[AgentProfile]:
        """List profiles that are actually selectable in the current IM runtime.

        A profile is selectable when it is bound to a node and its ownership matches
        the current runtime state for that node. Fresh canonical runtimes advertise
        agents before any bind exists, so ownerless node/profile pairs must still be
        visible. Once a node is bound, only same-owner profiles (or freshly advertised
        blank-owner rows waiting to be reassigned) should remain selectable.
        """
        rows = self._connection.execute(
            """
            SELECT ap.agent_id, ap.owner_id, ap.node_id, ap.display_name, ap.description, ap.system_prompt, ap.skills_json,
                   ap.tool_allowlist_json, ap.group_reply_policy, ap.default_model, ap.workspace_root, ap.profile_version,
                   ap.is_stale, ap.features_json, ap.custom_prompt, ap.heartbeat_json
            FROM agent_profiles ap
            JOIN nodes n ON n.node_id = ap.node_id
            WHERE ap.node_id IS NOT NULL
              AND ap.node_id != ''
              AND ap.is_stale = 0
              AND (
                    (COALESCE(n.owner_id, '') = '' AND ap.owner_id = '')
                 OR (COALESCE(n.owner_id, '') != '' AND (ap.owner_id = '' OR ap.owner_id = n.owner_id))
              )
            ORDER BY ap.created_at, ap.rowid
            """
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def list_runtime_selectable_profiles_for_owner(
        self, *, owner_id: str
    ) -> list[AgentProfile]:
        """Owner-scoped runtime-selectable profile list (cross-tenant safe).

        Filters to either:
        - profiles owned by the caller (``ap.owner_id = owner_id``), OR
        - ownerless profiles advertised by ownerless runtimes (fresh nodes pre-bind),
          so any authenticated user can discover and bind them.

        A profile owned by another tenant is never returned, regardless of node state.
        """
        rows = self._connection.execute(
            """
            SELECT ap.agent_id, ap.owner_id, ap.node_id, ap.display_name, ap.description, ap.system_prompt, ap.skills_json,
                   ap.tool_allowlist_json, ap.group_reply_policy, ap.default_model, ap.workspace_root, ap.profile_version,
                   ap.is_stale, ap.features_json, ap.custom_prompt, ap.heartbeat_json
            FROM agent_profiles ap
            JOIN nodes n ON n.node_id = ap.node_id
            WHERE ap.node_id IS NOT NULL
              AND ap.node_id != ''
              AND ap.is_stale = 0
              AND (
                    (ap.owner_id = ? AND COALESCE(n.owner_id, '') IN ('', ?))
                 OR (ap.owner_id = '' AND COALESCE(n.owner_id, '') = '')
              )
            ORDER BY ap.created_at, ap.rowid
            """,
            (owner_id, owner_id),
        ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile_for_owner(
        self, *, agent_id: str, owner_id: str
    ) -> AgentProfile | None:
        """Return the profile when owned by ``owner_id`` or ownerless (fresh, pre-bind); else None."""
        profile = self.get_profile(agent_id=agent_id)
        if profile is None:
            return None
        if profile.owner_id == owner_id or profile.owner_id == "":
            return profile
        return None

    def get_updated_at(self, *, agent_id: str) -> str | None:
        """Return the last update timestamp for one agent profile."""
        row = self._connection.execute(
            "SELECT updated_at FROM agent_profiles WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        value = row["updated_at"]
        return str(value) if value is not None else None

    def get_profile(self, *, agent_id: str) -> AgentProfile | None:
        """Return one agent profile, or None when it does not exist."""
        row = self._connection.execute(
            """
            SELECT agent_id, owner_id, node_id, display_name, description, system_prompt, skills_json,
                   tool_allowlist_json, group_reply_policy, default_model, workspace_root, profile_version,
                   is_stale, features_json, custom_prompt, heartbeat_json
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
        workspace_root: str | None,
        node_id: str | None = None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
    ) -> "AgentProfile":
        """Create or replace one seed profile without optimistic locking."""
        created_at = _utc_now()
        skills_json = _encode_json_list(skills)
        tool_allowlist_json = _encode_json_list(tool_allowlist)
        # feat-379-M2: persist per-agent feature flags and custom prompt.
        # feat-379-M6 (ISSUE-2): when features/custom_prompt are None (omitted by caller),
        # keep whatever is already in the DB so Gateway re-registration on restart does not
        # wipe user edits.  The ON CONFLICT clause uses COALESCE to fall back to the
        # existing row value when the incoming JSON is the empty-object sentinel '{}' / NULL.
        features_json = (
            json.dumps(features, ensure_ascii=False) if features is not None else None
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO agent_profiles(
                    agent_id, owner_id, node_id, display_name, description, system_prompt,
                    skills_json, tool_allowlist_json, group_reply_policy,
                    default_model, workspace_root, profile_version, created_at, updated_at,
                    features_json, custom_prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, '{}'), ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    node_id = excluded.node_id,
                    display_name = excluded.display_name,
                    description = excluded.description,
                    system_prompt = excluded.system_prompt,
                    skills_json = excluded.skills_json,
                    tool_allowlist_json = excluded.tool_allowlist_json,
                    group_reply_policy = excluded.group_reply_policy,
                    default_model = excluded.default_model,
                    workspace_root = excluded.workspace_root,
                    updated_at = excluded.updated_at,
                    is_stale = 0,
                    staled_at = NULL,
                    features_json = CASE
                        WHEN excluded.features_json IS NOT NULL AND excluded.features_json != '{}'
                        THEN excluded.features_json
                        ELSE agent_profiles.features_json
                    END,
                    custom_prompt = CASE
                        WHEN excluded.custom_prompt IS NOT NULL
                        THEN excluded.custom_prompt
                        ELSE agent_profiles.custom_prompt
                    END
                """,
                (
                    agent_id,
                    owner_id,
                    node_id,
                    display_name,
                    description,
                    system_prompt,
                    skills_json,
                    tool_allowlist_json,
                    group_reply_policy,
                    default_model,
                    workspace_root,
                    1,
                    created_at,
                    created_at,
                    features_json,
                    custom_prompt,
                ),
            )
        profile = self.get_profile(agent_id=agent_id)
        assert profile is not None
        return profile

    def mark_stale_for_node(
        self,
        *,
        node_id: str,
        advertised_agent_ids: list[str],
    ) -> int:
        """Mark as stale any agent profile for this node not in the current advertise list.

        Returns the count of rows newly marked stale. Safe to call repeatedly; rows
        already stale are excluded from the count (is_stale=0 guard).
        Empty advertised_agent_ids marks all profiles for this node as stale.
        """
        now = _utc_now()
        if advertised_agent_ids:
            placeholders = ",".join("?" * len(advertised_agent_ids))
            params: list[object] = [now, node_id] + list(advertised_agent_ids)
            cursor = self._connection.execute(
                f"""
                UPDATE agent_profiles
                SET is_stale = 1, staled_at = ?
                WHERE node_id = ?
                  AND is_stale = 0
                  AND agent_id NOT IN ({placeholders})
                """,
                params,
            )
        else:
            cursor = self._connection.execute(
                """
                UPDATE agent_profiles
                SET is_stale = 1, staled_at = ?
                WHERE node_id = ?
                  AND is_stale = 0
                """,
                (now, node_id),
            )
        return cursor.rowcount

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
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
        heartbeat_json: str | None = None,
    ) -> "AgentProfile":
        """Update a profile with optimistic locking on profile_version.

        workspace_root is intentionally excluded from this method — it is set
        once at agent creation and is immutable afterwards (bugfix-404-M2
        decision 5).  Any call-site passing workspace_root via the service
        layer would silently reset it to the managed default; removing the
        parameter makes that a compile-time error instead.
        """
        current = self.get_profile(agent_id=agent_id)
        if current is None:
            raise ValueError("agent_id not found")
        if current.profile_version != profile_version:
            raise AgentProfileVersionConflictError("profile_version conflict")
        updated_at = _utc_now()
        next_version = current.profile_version + 1
        # feat-379-M2: persist per-agent feature flags and custom prompt
        features_json = json.dumps(
            features if features is not None else dict(current.features),
            ensure_ascii=False,
        )
        resolved_custom_prompt = (
            custom_prompt if custom_prompt is not None else current.custom_prompt
        )
        # feat-394: heartbeat_json carries cadence (every/active_hours); None preserves existing.
        # feat-394 M9-E: cron_json removed — cron enable lives in features_json["cron_scheduling"].
        resolved_heartbeat_json = (
            heartbeat_json if heartbeat_json is not None else current.heartbeat_json
        )
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
                    updated_at = ?,
                    features_json = ?,
                    custom_prompt = ?,
                    heartbeat_json = ?
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
                    features_json,
                    resolved_custom_prompt,
                    resolved_heartbeat_json,
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

    def _row_to_profile(self, row: sqlite3.Row) -> "AgentProfile":
        """Convert one storage row to a domain agent profile."""
        keys = row.keys()
        is_stale = bool(row["is_stale"]) if "is_stale" in keys else False
        # feat-379-M2: decode per-agent feature flags (stored as JSON object)
        raw_features = row["features_json"] if "features_json" in keys else None
        if raw_features:
            try:
                decoded_features = json.loads(raw_features)
                features = (
                    {
                        k: bool(v)
                        for k, v in decoded_features.items()
                        if isinstance(k, str)
                    }
                    if isinstance(decoded_features, dict)
                    else {}
                )
            except (ValueError, TypeError):
                features = {}
        else:
            features = {}
        custom_prompt_raw = row["custom_prompt"] if "custom_prompt" in keys else None
        custom_prompt = (
            custom_prompt_raw
            if isinstance(custom_prompt_raw, str) and custom_prompt_raw.strip()
            else None
        )
        # feat-394: heartbeat cadence JSON string (raw, not decoded; forwarded to gateway as-is)
        # feat-394 M9-E: cron_json removed — cron enable lives in features["cron_scheduling"].
        heartbeat_json_raw = row["heartbeat_json"] if "heartbeat_json" in keys else None
        heartbeat_json = (
            heartbeat_json_raw
            if isinstance(heartbeat_json_raw, str) and heartbeat_json_raw.strip()
            else None
        )
        return AgentProfile(
            agent_id=row["agent_id"],
            owner_id=row["owner_id"],
            node_id=row["node_id"],
            display_name=row["display_name"],
            description=row["description"],
            system_prompt=row["system_prompt"],
            skills=_decode_string_list(row["skills_json"]),
            tool_allowlist=_decode_string_list(row["tool_allowlist_json"]),
            group_reply_policy=row["group_reply_policy"],
            default_model=row["default_model"],
            workspace_root=row["workspace_root"],
            profile_version=int(row["profile_version"]),
            is_stale=is_stale,
            features=features,
            custom_prompt=custom_prompt,
            heartbeat_json=heartbeat_json,
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
                (
                    node_id,
                    owner_id,
                    node_name,
                    normalized_status,
                    "",
                    0,
                    version,
                    1,
                    1,
                    None,
                    None,
                ),
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
                (
                    node_id,
                    owner_id,
                    node_name,
                    "online",
                    _utc_now(),
                    max(agent_count, 0),
                    version,
                    1,
                    1,
                    None,
                    None,
                ),
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
        next_status = _normalize_node_status(
            status=reported_status, last_error=last_error
        )
        next_agent_count = (
            existing.agent_count if agent_count is None else max(agent_count, 0)
        )
        next_version = existing.version if version is None else version
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                SET status = ?, last_heartbeat_at = ?, agent_count = ?, version = ?, last_error = ?
                WHERE node_id = ?
                """,
                (
                    next_status,
                    _utc_now(),
                    next_agent_count,
                    next_version,
                    last_error,
                    node_id,
                ),
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

    def list_nodes_for_owner(self, *, owner_id: str) -> list[NodeStatus]:
        """Owner-scoped list — guarantees no cross-tenant leakage at the SQL layer."""
        rows = self._connection.execute(
            """
            SELECT node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version,
                   relay_enabled, reporting_enabled, alias, last_error
            FROM nodes
            WHERE owner_id = ?
            ORDER BY CASE status WHEN 'online' THEN 0 WHEN 'degraded' THEN 1 ELSE 2 END,
                     COALESCE(last_heartbeat_at, '') DESC,
                     rowid DESC
            """,
            (owner_id,),
        ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def get_node_for_owner(self, *, node_id: str, owner_id: str) -> NodeStatus | None:
        """Return the node only when its owner_id matches; else None."""
        node = self.get_node(node_id=node_id)
        if node is None or node.owner_id != owner_id:
            return None
        return node

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
        next_relay_enabled = (
            existing.relay_enabled if relay_enabled is None else relay_enabled
        )
        next_reporting_enabled = (
            existing.reporting_enabled
            if reporting_enabled is None
            else reporting_enabled
        )
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                SET alias = ?, relay_enabled = ?, reporting_enabled = ?
                WHERE node_id = ?
                """,
                (
                    next_alias,
                    int(next_relay_enabled),
                    int(next_reporting_enabled),
                    node_id,
                ),
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

    def create_bind_request(
        self, *, node_id: str, bind_base_url: str
    ) -> DeviceBindRequest:
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
                (
                    bind_id,
                    node_id,
                    None,
                    "pending",
                    bind_token,
                    bind_url,
                    created_at,
                    None,
                ),
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

    def get_bind_request_by_token(self, *, bind_token: str) -> DeviceBindRequest | None:
        """Return one bind request by token, or None when missing."""
        row = self._connection.execute(
            "SELECT bind_id, node_id, user_id, status, bind_token, bind_url, created_at, confirmed_at FROM bind_requests WHERE bind_token = ?",
            (bind_token,),
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

    def confirm_bind_request(
        self, *, bind_id: str | None = None, bind_token: str | None = None, user_id: str
    ) -> DeviceBindRequest:
        """Mark one pending bind request as confirmed for a user."""
        resolved_bind_id = bind_id
        if resolved_bind_id is None:
            if bind_token is None:
                raise ValueError("bind_id not found")
            bind = self.get_bind_request_by_token(bind_token=bind_token)
            if bind is None:
                raise ValueError("bind_token not found")
            resolved_bind_id = bind.bind_id
        confirmed_at = _utc_now()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE bind_requests
                SET user_id = ?, status = ?, confirmed_at = ?
                WHERE bind_id = ? AND status = 'pending'
                """,
                (user_id, "confirmed", confirmed_at, resolved_bind_id),
            )
        if cursor.rowcount == 0:
            existing = self.get_bind_request(bind_id=resolved_bind_id)
            if existing is None:
                raise ValueError("bind_id not found")
            raise ValueError("bind request already confirmed")
        request = self.get_bind_request(bind_id=resolved_bind_id)
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
        created_at = _utc_now()
        payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        preview = _preview_from_event(event_type=event_type, payload=payload)
        with self._connection:
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
                    payload_json,
                    created_at,
                ),
            )
            if preview is not None:
                self._connection.execute(
                    "UPDATE conversations SET last_message_preview = ?, last_message_at = ? WHERE id = ?",
                    (preview, created_at, conversation_id),
                )
        event = ConversationEvent(
            event_id=int(cursor.lastrowid),
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=event_type,
            delivery_status=delivery_status,
            payload_json=payload_json,
            created_at=created_at,
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


def _encode_json_list(values: list[str]) -> str:
    """Encode string lists with a stable JSON representation."""
    return json.dumps(
        [str(item) for item in values], ensure_ascii=True, separators=(",", ":")
    )


def _decode_string_list(raw_value: str) -> list[str]:
    """Decode a JSON list into a list of strings."""
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded]


def _resolve_usage_scope(
    *, owner_id: str | None, conversation_id: str | None, agent_id: str | None
) -> tuple[str, str | None]:
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


_UNSET: object = object()


def _normalize_tool_calls(tool_calls: list[ToolCall] | None) -> list[ToolCall] | None:
    """Return tool_calls list passthrough, validating non-None entries by construction."""
    if tool_calls is None:
        return None
    return list(tool_calls)


def _tool_call_to_dict(tool_call: ToolCall) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": tool_call.id,
        "name": tool_call.name,
        "status": tool_call.status,
        "input": tool_call.input,
    }
    if tool_call.duration_ms is not None:
        payload["duration_ms"] = tool_call.duration_ms
    if tool_call.output is not None:
        payload["output"] = tool_call.output
    # bugfix-410-M2 (#97): persist sidecar badge reason alongside the call.
    if tool_call.reason is not None:
        payload["reason"] = tool_call.reason
    if tool_call.detail is not None:
        payload["detail"] = tool_call.detail
    # feat-425: persist tool-carried emoji alongside detail (omit when unset).
    if tool_call.emoji is not None:
        payload["emoji"] = tool_call.emoji
    # feat-434-M1: persist the user-decision verdict (omit when unset).
    if tool_call.approval is not None:
        payload["approval"] = tool_call.approval
    # feat-439-M2: persist the shared process-timeline seq (omit when unset/legacy).
    if tool_call.seq is not None:
        payload["seq"] = tool_call.seq
    return payload


def _encode_tool_calls(tool_calls: list[ToolCall]) -> str:
    return json.dumps(
        [_tool_call_to_dict(tc) for tc in tool_calls],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _load_permission_requests(raw_value: object) -> list[dict]:
    """Parse permission_request_json (always list-shaped, bugfix-367).

    开发态实现:列里必须存 list。坏数据(非 list / 解析失败)直接返回空 list,
    呼叫方可以从干净基线开始重试。不做旧 dict 形态的兼容(参见 fix.md "修复"段
    第二节:开发态,不做数据兼容)。
    """
    if raw_value is None:
        return []
    if not isinstance(raw_value, str) or not raw_value.strip():
        return []
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [dict(item) for item in parsed if isinstance(item, dict)]


def _decode_tool_calls(value: object) -> list[ToolCall] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    out: list[ToolCall] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                ToolCall(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    status=str(item.get("status", "")),
                    duration_ms=(
                        int(item["duration_ms"])
                        if isinstance(item.get("duration_ms"), (int, float))
                        else None
                    ),
                    input=dict(item.get("input"))
                    if isinstance(item.get("input"), dict)
                    else {},
                    output=item.get("output")
                    if isinstance(item.get("output"), str)
                    else None,
                    reason=item.get("reason")
                    if isinstance(item.get("reason"), str)
                    else None,
                    detail=item.get("detail")
                    if isinstance(item.get("detail"), dict)
                    else None,
                    emoji=item.get("emoji")
                    if isinstance(item.get("emoji"), str)
                    else None,
                    approval=item.get("approval")
                    if isinstance(item.get("approval"), str)
                    else None,
                    seq=item.get("seq") if isinstance(item.get("seq"), int) else None,
                )
            )
        except ValueError:
            # Malformed historical row — surface loudly: better than silently dropping a row's tool history.
            raise
    return out


def _next_process_seq(thinking: list[ThinkingSegment], tools: list[ToolCall]) -> int:
    """feat-439-M2: 下一个「过程项」seq = 思考与工具现有 seq 的 max + 1（从 0 起）。

    思考与工具共享这一个 per-message 计数器，按真实到达序单调递增、全局唯一 —— 渲染端
    据此 merge 成时间线，唯一性让 live 事件可幂等去重。旧工具行 seq 为 None，忽略。
    """
    seqs = [s.seq for s in thinking]
    seqs += [t.seq for t in tools if t.seq is not None]
    return (max(seqs) + 1) if seqs else 0


def _encode_thinking(segments: list[ThinkingSegment]) -> str:
    return json.dumps(
        [{"seq": int(s.seq), "text": s.text} for s in segments],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _decode_thinking(value: object) -> list[ThinkingSegment] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    out: list[ThinkingSegment] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            ThinkingSegment(
                seq=int(item["seq"]) if isinstance(item.get("seq"), int) else 0,
                text=str(item.get("text", "")),
            )
        )
    return out or None


def _encode_token_usage(usage: TokenUsage | None) -> str | None:
    if usage is None:
        return None
    return json.dumps(
        {
            "output": int(usage.output),
            "context_used": int(usage.context_used),
            "context_window": int(usage.context_window),
            "total": int(usage.total),
            # feat-439-M1: 缓存命中两字段持久化。
            "cache_read_tokens": int(usage.cache_read_tokens),
            "cache_total_input_tokens": int(usage.cache_total_input_tokens),
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _decode_token_usage(value: object) -> TokenUsage | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    try:
        output = int(parsed["output"])
        context_used = int(parsed["context_used"])
        context_window = int(parsed["context_window"])
        # bugfix-390 FIX-1: pre-M17 rows have "total": null in JSON.
        # parsed.get("total", 0) returns None when the key exists with a null value
        # (dict.get default only fires when the key is absent), so int(None) would
        # raise TypeError → the except block silently returned None → chip not rendered.
        # Derive total here — this is the single authoritative decode entry point.
        _raw_total = parsed.get("total")
        total = int(_raw_total) if _raw_total is not None else context_used + output
        # feat-439-M1: 旧行无缓存字段 → 默认 0(同 total 兜底思路，缺键不致整体解码失败)。
        _raw_cache_read = parsed.get("cache_read_tokens")
        cache_read = int(_raw_cache_read) if _raw_cache_read is not None else 0
        _raw_cache_total = parsed.get("cache_total_input_tokens")
        cache_total_input = int(_raw_cache_total) if _raw_cache_total is not None else 0
        return TokenUsage(
            output=output,
            context_used=context_used,
            context_window=context_window,
            total=total,
            cache_read_tokens=cache_read,
            cache_total_input_tokens=cache_total_input,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _visible_content_from_event(
    *, event_type: str, payload: dict[str, object]
) -> str | None:
    """Return the visible bubble content represented by one event payload."""
    return _preview_from_event(event_type, payload)


def _synthetic_message_id_from_event_payload(payload: dict[str, object]) -> str | None:
    """Build the same stable synthetic message ids used by the frontend relay mapper."""
    message_id = _optional_text(payload.get("message_id"))
    if message_id is None:
        return None
    relay_task_id = _optional_text(payload.get("relay_task_id"))
    if relay_task_id is not None:
        return f"{message_id}:relay:{relay_task_id}"
    agent_id = _optional_text(payload.get("agent_id"))
    if agent_id is not None:
        return f"{message_id}:agent:{agent_id}"
    return f"{message_id}:agent"


def _upsert_message(messages: list[Message], candidate: Message) -> list[Message]:
    """Insert or refresh one message while preserving chronological ordering."""
    existing_index = next(
        (index for index, item in enumerate(messages) if item.id == candidate.id), -1
    )
    if existing_index == -1:
        return _sort_messages(messages + [candidate])
    existing = messages[existing_index]
    next_messages = list(messages)
    next_messages[existing_index] = Message(
        id=existing.id,
        conversation_id=existing.conversation_id,
        sender_user_id=candidate.sender_user_id,
        sender_type=candidate.sender_type,
        sender=candidate.sender,
        content=candidate.content
        if len(candidate.content) >= len(existing.content)
        else existing.content,
        attachments=candidate.attachments
        if candidate.attachments
        else existing.attachments,
        delivery_status=candidate.delivery_status,
        created_at=candidate.created_at,
    )
    return _sort_messages(next_messages)


def _sort_messages(messages: list[Message]) -> list[Message]:
    """Return messages ordered by created_at, then stable id."""
    return sorted(messages, key=lambda item: (item.created_at, item.id))


def _to_message_preview(*, content: str, attachments: list[Attachment]) -> str:
    """Choose the best lightweight inbox preview for one persisted message."""
    normalized_content = content.strip()
    if normalized_content:
        return normalized_content
    first_attachment = attachments[0] if attachments else None
    if first_attachment and first_attachment.file_name:
        return first_attachment.file_name
    return ""


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
                content_type=str(content_type)
                if content_type not in {None, ""}
                else None,
                file_name=str(file_name) if file_name not in {None, ""} else None,
            )
        )
    return results


def _format_utc(dt: datetime) -> str:
    """Format a UTC datetime into the canonical ``...Z`` storage string.

    Single source of truth for the on-disk timestamp text. Any value compared by
    SQL string ordering against a stored timestamp (e.g. relay_watchdog cutoffs vs
    ``awaiting_permission_at``) must be produced here so the two formats can never
    drift apart — a mismatch would silently break the textual comparison.

    Requires a timezone-aware datetime. A naive value is rejected fail-fast: it
    would format without the ``+00:00`` offset, so the ``Z`` substitution would
    no-op and the stored text would silently drift from every other timestamp.
    Aware values in any zone are normalised to UTC before formatting, so callers
    cannot accidentally store a non-UTC offset.
    """
    if dt.tzinfo is None:
        raise ValueError("_format_utc requires a timezone-aware datetime")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    """Return current UTC time formatted for storage."""
    return _format_utc(datetime.now(timezone.utc))
