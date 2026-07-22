"""SQLite repositories for IM users, conversations, and messages."""

from collections.abc import Callable
import sqlite3
from uuid import uuid4

from IM.domain.models import (
    AgentConfigChangedBoundary,
    ConversationEvent,
)


from IM.infra._timestamps import utc_now
from IM.infra.repositories._event_rows import insert_event_row


class AgentConfigBoundaryRepository:
    """Persist non-message runtime-cache boundaries and their replay events."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        notify: Callable[[ConversationEvent], None] | None = None,
    ) -> None:
        self._connection = connection
        self._notify = notify

    def record_from_gateway(
        self,
        *,
        boundary_id: str,
        node_id: str,
        owner_id: str,
        conversation_id: str,
        agent_id: str,
        before_message_id: str,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        applied_at: str,
    ) -> AgentConfigChangedBoundary:
        """Durably record a Gateway-confirmed boundary after ownership validation.

        Raises:
            ValueError: When the Gateway, conversation, agent, or anchor do not form
                one owned conversation, or a reused boundary id changes its payload.
        """
        if profile_version is not None and profile_version < 0:
            raise ValueError("profile_version must be non-negative when present")
        conversation = self._connection.execute(
            "SELECT owner_id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if conversation is None:
            raise ValueError("conversation_id not found")
        if owner_id and str(conversation["owner_id"]) != owner_id:
            raise ValueError("conversation is outside gateway owner scope")
        anchor = self._connection.execute(
            "SELECT conversation_id FROM messages WHERE id = ?", (before_message_id,)
        ).fetchone()
        if anchor is None or str(anchor["conversation_id"]) != conversation_id:
            raise ValueError("before_message_id is not in conversation")
        agent = self._connection.execute(
            """
            SELECT agent_profiles.node_id
            FROM conversation_participants
            JOIN users ON users.id = conversation_participants.user_id
            JOIN agent_profiles ON agent_profiles.agent_id = substr(users.username, 7)
            WHERE conversation_participants.conversation_id = ?
              AND users.username = ?
            """,
            (conversation_id, f"agent:{agent_id}"),
        ).fetchone()
        if agent is None:
            raise ValueError("agent_id is not a conversation participant")
        if str(agent["node_id"] or "") != node_id:
            raise ValueError("agent_id is not hosted by gateway node")
        return self._record(
            boundary_id=boundary_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            before_message_id=before_message_id,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
            applied_at=applied_at,
        )

    def copy_boundary(
        self,
        *,
        source: AgentConfigChangedBoundary,
        conversation_id: str,
        before_message_id: str,
    ) -> AgentConfigChangedBoundary:
        """Copy a pre-fork boundary onto its mapped target anchor."""
        return self._record(
            boundary_id=uuid4().hex,
            conversation_id=conversation_id,
            agent_id=source.agent_id,
            before_message_id=before_message_id,
            runtime_fingerprint=source.runtime_fingerprint,
            fingerprint_schema=source.fingerprint_schema,
            profile_version=source.profile_version,
            applied_at=source.applied_at,
        )

    def list_for_message_ids(
        self, *, conversation_id: str, message_ids: list[str]
    ) -> dict[str, list[AgentConfigChangedBoundary]]:
        """Return boundaries keyed by their anchor message in stable event order."""
        if not message_ids:
            return {}
        placeholders = ", ".join("?" for _ in message_ids)
        rows = self._connection.execute(
            f"""
            SELECT boundary_id, conversation_id, agent_id, before_message_id,
                   runtime_fingerprint, fingerprint_schema, profile_version,
                   applied_at, event_id
            FROM agent_config_boundaries
            WHERE conversation_id = ? AND before_message_id IN ({placeholders})
            ORDER BY event_id
            """,
            (conversation_id, *message_ids),
        ).fetchall()
        result: dict[str, list[AgentConfigChangedBoundary]] = {}
        for row in rows:
            boundary = self._boundary_from_row(row)
            result.setdefault(boundary.before_message_id, []).append(boundary)
        return result

    def list_all(self, *, conversation_id: str) -> list[AgentConfigChangedBoundary]:
        """Return all boundaries in durable insertion order for fork projection."""
        rows = self._connection.execute(
            """
            SELECT boundary_id, conversation_id, agent_id, before_message_id,
                   runtime_fingerprint, fingerprint_schema, profile_version,
                   applied_at, event_id
            FROM agent_config_boundaries
            WHERE conversation_id = ?
            ORDER BY event_id
            """,
            (conversation_id,),
        ).fetchall()
        return [self._boundary_from_row(row) for row in rows]

    def _record(
        self,
        *,
        boundary_id: str,
        conversation_id: str,
        agent_id: str,
        before_message_id: str,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
        applied_at: str,
    ) -> AgentConfigChangedBoundary:
        existing_by_id = self._connection.execute(
            """
            SELECT boundary_id, conversation_id, agent_id, before_message_id,
                   runtime_fingerprint, fingerprint_schema, profile_version,
                   applied_at, event_id
            FROM agent_config_boundaries WHERE boundary_id = ?
            """,
            (boundary_id,),
        ).fetchone()
        if existing_by_id is not None:
            existing = self._boundary_from_row(existing_by_id)
            if (
                existing.conversation_id != conversation_id
                or existing.agent_id != agent_id
                or existing.before_message_id != before_message_id
                or existing.runtime_fingerprint != runtime_fingerprint
                or existing.fingerprint_schema != fingerprint_schema
                or existing.profile_version != profile_version
                or existing.applied_at != applied_at
            ):
                raise ValueError("boundary_id conflicts with persisted boundary")
            return existing
        existing_natural = self._connection.execute(
            """
            SELECT boundary_id, conversation_id, agent_id, before_message_id,
                   runtime_fingerprint, fingerprint_schema, profile_version,
                   applied_at, event_id
            FROM agent_config_boundaries
            WHERE conversation_id = ? AND before_message_id = ? AND runtime_fingerprint = ?
            """,
            (conversation_id, before_message_id, runtime_fingerprint),
        ).fetchone()
        if existing_natural is not None:
            return self._boundary_from_row(existing_natural)
        payload = {
            "id": boundary_id,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "before_message_id": before_message_id,
            "applied_at": applied_at,
        }
        event_created_at = utc_now()
        event: ConversationEvent
        with self._connection:
            event = insert_event_row(
                self._connection,
                conversation_id=conversation_id,
                message_id=None,
                event_type="agent.config.changed",
                delivery_status="completed",
                payload=payload,
                created_at=event_created_at,
            )
            self._connection.execute(
                """
                INSERT INTO agent_config_boundaries(
                    boundary_id, conversation_id, agent_id, before_message_id,
                    runtime_fingerprint, fingerprint_schema, profile_version,
                    applied_at, event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    boundary_id,
                    conversation_id,
                    agent_id,
                    before_message_id,
                    runtime_fingerprint,
                    fingerprint_schema,
                    profile_version,
                    applied_at,
                    event.event_id,
                ),
            )
        boundary = AgentConfigChangedBoundary(
            id=boundary_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            before_message_id=before_message_id,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
            applied_at=applied_at,
            event_id=event.event_id,
        )
        if self._notify is not None:
            self._notify(event)
        return boundary

    @staticmethod
    def _boundary_from_row(row: sqlite3.Row) -> AgentConfigChangedBoundary:
        return AgentConfigChangedBoundary(
            id=str(row["boundary_id"]),
            conversation_id=str(row["conversation_id"]),
            agent_id=str(row["agent_id"]),
            before_message_id=str(row["before_message_id"]),
            runtime_fingerprint=str(row["runtime_fingerprint"]),
            fingerprint_schema=str(row["fingerprint_schema"]),
            profile_version=(
                int(row["profile_version"])
                if row["profile_version"] is not None
                else None
            ),
            applied_at=str(row["applied_at"]),
            event_id=int(row["event_id"]),
        )
