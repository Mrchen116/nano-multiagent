"""SQLite repositories for IM users, conversations, and messages."""

from dataclasses import dataclass
import sqlite3
from uuid import uuid4

from IM.domain.models import (
    Actor,
    Conversation,
)


from IM.infra._timestamps import utc_now

_ACTIVE_AGENT_DELIVERY_STATUSES = frozenset({"sent", "running"})


@dataclass(frozen=True, slots=True)
class _ConversationConfigSnapshot:
    """Frozen agent config captured when a conversation is created."""

    agent_id: str | None
    profile_version: int | None


@dataclass(frozen=True, slots=True)
class ExternalConversationWriteResult:
    """Result of an idempotent external conversation write."""

    conversation: Conversation
    created: bool


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
        target_node_id: str | None = None,
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
            target_node_id: Optional server-owned route pin for a direct conversation.

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
        normalized_target_node_id = target_node_id.strip() if target_node_id else None

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
        created_at = utc_now()
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
                    external_source,
                    external_chat_id,
                    target_node_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    None,
                    None,
                    normalized_target_node_id,
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
            config_agent_id=config_snapshot.agent_id,
            created_at=created_at,
            participants=[self._actor_from_user_row(row) for row in ordered_rows],
            source_agent_id=config_snapshot.agent_id,
            target_node_id=normalized_target_node_id,
        )

    def find_or_create_external_conversation(
        self,
        *,
        external_source: str,
        external_chat_id: str,
        agent_id: str,
        title: str,
        is_group: bool,
        participant_ids: list[str],
        owner_id: str,
        creator_id: str,
    ) -> ExternalConversationWriteResult:
        """Idempotently write one external-channel shadow conversation.

        Returns:
            The durable conversation and whether this call created it.
        """
        normalized_source = external_source.strip()
        normalized_chat_id = external_chat_id.strip()
        normalized_agent_id = agent_id.strip()
        normalized_owner_id = owner_id.strip()
        if not normalized_source:
            raise ValueError("external_source must be non-empty")
        if not normalized_chat_id:
            raise ValueError("external_chat_id must be non-empty")
        if not normalized_agent_id:
            raise ValueError("agent_id must be non-empty")
        if not normalized_owner_id:
            raise ValueError("owner_id must be non-empty")
        if not title.strip():
            raise ValueError("title must be non-empty")

        existing = self._connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE external_source = ?
              AND external_chat_id = ?
              AND config_agent_id = ?
              AND owner_id = ?
            """,
            (
                normalized_source,
                normalized_chat_id,
                normalized_agent_id,
                normalized_owner_id,
            ),
        ).fetchone()
        if existing is not None:
            with self._connection:
                self._connection.execute(
                    "UPDATE conversations SET title = ?, type = ? WHERE id = ?",
                    (
                        " ".join(title.split()),
                        "group" if is_group else "direct",
                        existing["id"],
                    ),
                )
            found = self.get_conversation(conversation_id=str(existing["id"]))
            assert found is not None
            return ExternalConversationWriteResult(conversation=found, created=False)

        normalized_references = list(
            dict.fromkeys(
                participant_id.strip()
                for participant_id in participant_ids
                if participant_id.strip()
            )
        )
        if not normalized_references:
            raise ValueError("participant_ids must not be empty")
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
        creator_row = self._resolve_participant_user_row(reference=creator_id)
        if creator_row is None:
            raise ValueError("creator_id not found")
        resolved_creator_id = str(creator_row["id"])
        if resolved_creator_id not in normalized_participants:
            raise ValueError("creator_id must be one of participant_ids")
        profile_row = self._connection.execute(
            "SELECT profile_version FROM agent_profiles WHERE agent_id = ?",
            (normalized_agent_id,),
        ).fetchone()
        profile_version = (
            int(profile_row["profile_version"]) if profile_row is not None else None
        )
        conversation_id = uuid4().hex
        created_at = utc_now()
        conversation_type = "group" if is_group else "direct"
        try:
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
                        external_source,
                        external_chat_id,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        " ".join(title.split()),
                        conversation_type,
                        normalized_owner_id,
                        resolved_creator_id,
                        0,
                        0,
                        0,
                        None,
                        None,
                        normalized_agent_id,
                        profile_version,
                        normalized_source,
                        normalized_chat_id,
                        created_at,
                    ),
                )
                self._connection.executemany(
                    "INSERT INTO conversation_participants(conversation_id, user_id) VALUES (?, ?)",
                    [(conversation_id, user_id) for user_id in normalized_participants],
                )
        except sqlite3.IntegrityError:
            existing_after_race = self._connection.execute(
                """
                SELECT id
                FROM conversations
                WHERE external_source = ?
                  AND external_chat_id = ?
                  AND config_agent_id = ?
                  AND owner_id = ?
                """,
                (
                    normalized_source,
                    normalized_chat_id,
                    normalized_agent_id,
                    normalized_owner_id,
                ),
            ).fetchone()
            if existing_after_race is None:
                raise
            with self._connection:
                self._connection.execute(
                    "UPDATE conversations SET title = ?, type = ? WHERE id = ?",
                    (
                        " ".join(title.split()),
                        conversation_type,
                        existing_after_race["id"],
                    ),
                )
            found_after_race = self.get_conversation(
                conversation_id=str(existing_after_race["id"])
            )
            assert found_after_race is not None
            return ExternalConversationWriteResult(
                conversation=found_after_race,
                created=False,
            )
        created = self.get_conversation(conversation_id=conversation_id)
        assert created is not None
        return ExternalConversationWriteResult(conversation=created, created=True)

    def exists(self, conversation_id: str) -> bool:
        """Return whether a conversation row exists."""
        row = self._connection.execute(
            "SELECT 1 FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return row is not None

    def get_conversation(self, *, conversation_id: str) -> Conversation | None:
        """Load one conversation with participants."""
        row = self._connection.execute(
            """
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_agent_id, config_profile_version, external_source, external_chat_id, target_node_id, created_at
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
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_agent_id, config_profile_version, external_source, external_chat_id, target_node_id, created_at
            FROM conversations
            ORDER BY is_pinned DESC, COALESCE(last_message_at, created_at) DESC, rowid DESC
            """
        ).fetchall()
        return [self._row_to_conversation(row) for row in conversation_rows]

    def list_conversations_for_owner(self, *, owner_id: str) -> list[Conversation]:
        """Owner-scoped list — filters at the SQL layer to prevent cross-tenant leakage."""
        conversation_rows = self._connection.execute(
            """
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_agent_id, config_profile_version, external_source, external_chat_id, target_node_id, created_at
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
        config_agent_id = (
            row["config_agent_id"] if "config_agent_id" in row.keys() else None
        )
        row_keys = row.keys()
        configured_agent_id = (
            str(row["config_agent_id"])
            if "config_agent_id" in row_keys and row["config_agent_id"] is not None
            else None
        )
        # creator_id was added by M234 migration; fall back to owner_id for legacy rows.
        creator_id = (
            str(row["creator_id"]) if "creator_id" in row_keys else str(row["owner_id"])
        )
        participants = [self._actor_from_user_row(item) for item in participant_rows]
        source_agent_id = self._resolve_source_agent_id(
            configured_agent_id=configured_agent_id,
            participants=participants,
        )
        conversation_id = str(row["id"])
        return Conversation(
            id=conversation_id,
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
            config_agent_id=config_agent_id,
            config_profile_version=profile_version,
            external_source=row["external_source"]
            if "external_source" in row_keys
            else None,
            external_chat_id=row["external_chat_id"]
            if "external_chat_id" in row_keys
            else None,
            created_at=row["created_at"],
            participants=participants,
            run_state=self._resolve_run_state(conversation_id=conversation_id),
            source_agent_id=source_agent_id,
            source_node_id=self._resolve_source_node_id(
                source_agent_id=source_agent_id
            ),
            target_node_id=(
                str(row["target_node_id"])
                if "target_node_id" in row_keys and row["target_node_id"] is not None
                else None
            ),
        )

    @staticmethod
    def _resolve_source_agent_id(
        *, configured_agent_id: str | None, participants: list[Actor]
    ) -> str | None:
        """Return the single agent that owns the conversation transcript, if knowable."""
        if configured_agent_id:
            return configured_agent_id
        participant_agent_ids = sorted(
            {item.id for item in participants if item.type == "agent"}
        )
        if len(participant_agent_ids) == 1:
            return participant_agent_ids[0]
        return None

    def _resolve_run_state(self, *, conversation_id: str) -> str:
        """Derive conversation running state from live agent message rows."""
        placeholders = ", ".join("?" for _ in _ACTIVE_AGENT_DELIVERY_STATUSES)
        row = self._connection.execute(
            f"""
            SELECT 1
            FROM messages
            WHERE conversation_id = ?
              AND sender_type = 'agent'
              AND delivery_status IN ({placeholders})
            LIMIT 1
            """,
            (conversation_id, *_ACTIVE_AGENT_DELIVERY_STATUSES),
        ).fetchone()
        return "running" if row is not None else "idle"

    def _resolve_source_node_id(self, *, source_agent_id: str | None) -> str | None:
        """Project the owning Gateway identity without touching its workspace."""
        if not source_agent_id:
            return None
        profile_row = self._connection.execute(
            "SELECT node_id FROM agent_profiles WHERE agent_id = ?",
            (source_agent_id,),
        ).fetchone()
        if profile_row is None or profile_row["node_id"] is None:
            return None
        node_id = str(profile_row["node_id"]).strip()
        return node_id or None

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
            )
        return _ConversationConfigSnapshot(agent_id=None, profile_version=None)

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
                "SELECT agent_id, profile_version FROM agent_profiles WHERE agent_id = ?",
                (candidate_agent_id,),
            ).fetchone()
            if profile_row is None:
                continue
            return _ConversationConfigSnapshot(
                agent_id=str(profile_row["agent_id"]),
                profile_version=int(profile_row["profile_version"]),
            )
        return None
