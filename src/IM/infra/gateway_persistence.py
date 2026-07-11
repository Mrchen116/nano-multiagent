"""Concrete SQLite persistence operations for Gateway protocol workflows."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from IM.domain.models import NodeStatus, managed_workspace_root
from IM.infra.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    NodeRepository,
    UserRepository,
)


@dataclass(frozen=True, slots=True)
class GatewayRegistrationResult:
    """Describe the durable result of a completed Gateway registration."""

    previous_node: NodeStatus | None
    current_node: NodeStatus
    agent_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NodeTransition:
    """Describe node state before and after one lifecycle persistence operation."""

    previous_node: NodeStatus | None
    current_node: NodeStatus | None
    agent_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentRelayTarget:
    """Identify one peer agent and the node that can receive its relay."""

    agent_id: str
    node_id: str


@dataclass(frozen=True, slots=True)
class GroupReplyRoute:
    """Describe the persisted identities needed for a group-reply fanout."""

    sender_user_id: str
    sender_display_name: str
    targets: tuple[AgentRelayTarget, ...]


@dataclass(frozen=True, slots=True)
class DispatchTarget:
    """Represent one normalized outbound dispatch target."""

    kind: str
    id: str


@dataclass(frozen=True, slots=True)
class DispatchResolution:
    """Describe where an agent message lands and whether it has a relay node."""

    target: DispatchTarget
    conversation_id: str
    target_node_id: str | None


@dataclass(frozen=True, slots=True)
class AgentDispatchRecord:
    """Represent the durable first result for an idempotent agent dispatch."""

    dispatch_request_key: str
    source_agent_id: str
    target_kind: str
    target_id: str
    conversation_id: str
    message_id: str


class GatewayNodePersistence:
    """Persist Gateway node registration and status lifecycle on SQLite.

    Notes:
        Registration intentionally preserves the legacy repository commit sequence.
        This module does not add an operation-level transaction or lock: a failure
        while processing agent N leaves earlier committed node/profile/user rows
        durable exactly as before this seam existed.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind node lifecycle operations to the app-scoped SQLite connection."""
        self._connection = connection
        self._nodes = NodeRepository(connection)
        self._profiles = AgentProfileRepository(connection)
        self._users = UserRepository(connection)

    def register(
        self,
        *,
        node_id: str,
        node_name: str,
        version: str,
        agent_ids: list[str],
        agent_workspaces: dict[str, str],
    ) -> GatewayRegistrationResult:
        """Persist one node advertisement using the legacy durable write sequence.

        Args:
            node_id: Stable identifier supplied by the Gateway.
            node_name: Human-readable runtime name, already normalized by the caller.
            version: Gateway version string, or an empty string when omitted.
            agent_ids: Advertised agent identifiers in protocol order.
            agent_workspaces: Optional runtime workspace seed keyed by agent id.

        Returns:
            Previous/current node snapshots and agent ids in stable lexical order.

        Raises:
            sqlite3.DatabaseError: When any durable step fails. Earlier commits are
                deliberately retained; the operation is not atomic.

        Side Effects:
            Writes node, profile, synthetic agent-user, binding, and stale state.
        """
        previous_node = self._nodes.get_node(node_id=node_id)
        node = self._nodes.record_gateway_registration(
            node_id=node_id,
            node_name=node_name,
            version=version,
            agent_count=len(agent_ids),
        )
        for agent_id in agent_ids:
            existing = self._profiles.get_profile(agent_id=agent_id)
            owner_id = (
                existing.owner_id
                if existing is not None and existing.owner_id.strip()
                else (node.owner_id or "")
            )
            if existing is None:
                display_name = agent_id
                description = f"Runtime agent advertised by {node_name}."
                system_prompt = f"You are {agent_id}."
                skills: list[str] = []
                tool_allowlist: list[str] = []
                group_reply_policy = "MENTION"
                default_model: str | None = None
                workspace_root = agent_workspaces.get(
                    agent_id
                ) or managed_workspace_root(agent_id)
                features: dict[str, bool] | None = None
                custom_prompt: str | None = None
            else:
                display_name = existing.display_name
                description = existing.description
                system_prompt = existing.system_prompt
                skills = existing.skills
                tool_allowlist = existing.tool_allowlist
                group_reply_policy = existing.group_reply_policy
                default_model = existing.default_model
                workspace_root = existing.workspace_root or managed_workspace_root(
                    agent_id
                )
                features = existing.features
                custom_prompt = existing.custom_prompt
            if display_name == agent_id and agent_id.startswith("agent-"):
                display_name = (
                    agent_id.replace("agent-", "", 1).replace("-", " ").title()
                )
            self._profiles.upsert_profile(
                agent_id=agent_id,
                owner_id=owner_id,
                display_name=display_name,
                description=description,
                system_prompt=system_prompt,
                skills=skills,
                tool_allowlist=tool_allowlist,
                group_reply_policy=group_reply_policy,
                default_model=default_model,
                workspace_root=workspace_root,
                features=features,
                custom_prompt=custom_prompt,
            )
            if self._users.get_user_by_username(username=f"agent:{agent_id}") is None:
                self._users.create_user(
                    username=f"agent:{agent_id}",
                    display_name=display_name,
                )
            # Binding deliberately remains a separate uncommitted write here. The
            # next repository commit (or final commit below) is part of the legacy
            # failure semantics and must not be collapsed into an outer transaction.
            self._connection.execute(
                "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
                (node_id, agent_id),
            )
        self._profiles.mark_stale_for_node(
            node_id=node_id,
            advertised_agent_ids=list(agent_ids),
        )
        self._connection.commit()
        return GatewayRegistrationResult(
            previous_node=previous_node,
            current_node=node,
            agent_ids=tuple(sorted(agent_ids)),
        )

    def heartbeat(
        self,
        *,
        node_id: str,
        reported_status: str | None,
        agent_count: int | None,
        last_error: str | None,
        version: str | None,
    ) -> NodeTransition:
        """Persist a Gateway heartbeat and return its before/after status facts.

        Raises:
            ValueError: When the node has not registered.

        Side Effects:
            Updates the node heartbeat, aggregate status, count, version, and error.
        """
        previous_node = self._nodes.get_node(node_id=node_id)
        current_node = self._nodes.record_heartbeat(
            node_id=node_id,
            reported_status=reported_status,
            agent_count=agent_count,
            last_error=last_error,
            version=version,
        )
        return NodeTransition(
            previous_node=previous_node,
            current_node=current_node,
            agent_ids=self._agent_ids(node_id=node_id),
        )

    def mark_offline(
        self, *, node_id: str, last_error: str | None = None
    ) -> NodeTransition:
        """Mark an online/degraded node offline, optionally recording a reason.

        Args:
            node_id: Node to transition; a missing node is a no-op.
            last_error: Diagnostic reason to persist before the status flip. An
                already-offline node keeps its existing error unchanged.

        Returns:
            Before/after snapshots plus the node's agent ids. Missing nodes return
            two None snapshots; already-offline nodes return equal snapshots.

        Side Effects:
            May update last_error and status using the legacy separate commits.
        """
        previous_node = self._nodes.get_node(node_id=node_id)
        if previous_node is None:
            return NodeTransition(None, None, ())
        agent_ids = self._agent_ids(node_id=node_id)
        if previous_node.status == "offline":
            return NodeTransition(previous_node, previous_node, agent_ids)
        if last_error is not None:
            self._connection.execute(
                "UPDATE nodes SET last_error = ? WHERE node_id = ?",
                (last_error, node_id),
            )
            self._connection.commit()
        current_node = self._nodes.mark_disconnected(node_id=node_id)
        return NodeTransition(previous_node, current_node, agent_ids)

    def stale_online_node_ids(self, *, cutoff: str) -> tuple[str, ...]:
        """Return online nodes with heartbeats older than an ISO-8601 cutoff."""
        rows = self._connection.execute(
            """
            SELECT node_id FROM nodes
            WHERE status = 'online'
              AND last_heartbeat_at IS NOT NULL
              AND last_heartbeat_at < ?
            ORDER BY node_id
            """,
            (cutoff,),
        ).fetchall()
        return tuple(str(row["node_id"]) for row in rows)

    def _agent_ids(self, *, node_id: str) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT agent_id FROM agent_profiles WHERE node_id = ? ORDER BY agent_id",
            (node_id,),
        ).fetchall()
        return tuple(str(row["agent_id"]) for row in rows)


class GatewayConversationPersistence:
    """Persist Gateway conversation routing and dispatch knowledge on SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind delivery operations to the app-scoped SQLite connection."""
        self._connection = connection
        self._conversations = ConversationRepository(connection)
        self._profiles = AgentProfileRepository(connection)
        self._users = UserRepository(connection)

    def agent_user_id(self, *, agent_id: str) -> str | None:
        """Return the synthetic IM user id for an agent, or None when absent."""
        user = self._users.get_user_by_username(username=f"agent:{agent_id}")
        return user.id if user is not None else None

    def group_reply_route(
        self, *, conversation_id: str, source_agent_id: str
    ) -> GroupReplyRoute | None:
        """Resolve a group reply sender and its stably ordered deliverable peers.

        Returns:
            Sender identity and peers that currently have a node. Returns None when
            the conversation, sender, or any deliverable peer is absent.
        """
        conversation = self._conversations.get_conversation(
            conversation_id=conversation_id
        )
        source_user = self._users.get_user_by_username(
            username=f"agent:{source_agent_id}"
        )
        if conversation is None or source_user is None:
            return None
        targets: list[AgentRelayTarget] = []
        for participant_id in conversation.participant_ids:
            participant = self._users.get_user(user_id=participant_id)
            if participant is None or not participant.username.startswith("agent:"):
                continue
            peer_agent_id = participant.username[len("agent:") :].strip()
            if not peer_agent_id or peer_agent_id == source_agent_id:
                continue
            node_id = self.agent_node_id(agent_id=peer_agent_id)
            if node_id is not None:
                targets.append(
                    AgentRelayTarget(agent_id=peer_agent_id, node_id=node_id)
                )
        if not targets:
            return None
        return GroupReplyRoute(
            sender_user_id=source_user.id,
            sender_display_name=source_user.display_name,
            targets=tuple(sorted(targets, key=lambda item: item.agent_id)),
        )

    def resolve_send_target(
        self,
        *,
        source_agent_id: str,
        target: str,
        caller_owner_id: str | None,
    ) -> DispatchResolution:
        """Resolve a send target and create/reuse its canonical direct conversation.

        Args:
            source_agent_id: Agent sending the message.
            target: Explicit or implicit conversation, agent, or user reference.
            caller_owner_id: Owner policy supplied by the caller. None deliberately
                preserves the current agent-message behavior; this module never
                infers or repairs owner policy.

        Returns:
            Normalized target, landed conversation, and optional target node.

        Raises:
            ValueError: When source or target identity cannot be resolved.

        Side Effects:
            May create one direct conversation using the caller-supplied owner input.
        """
        source_user_id = self._require_user_id_by_username(
            username=f"agent:{source_agent_id}"
        )
        resolved_target = self._classify_dispatch_target(target=target)
        if resolved_target.kind == "conversation_id":
            conversation = self._conversations.get_conversation(
                conversation_id=resolved_target.id
            )
            if conversation is None:
                raise ValueError("conversation_id not found")
            return DispatchResolution(resolved_target, conversation.id, None)
        if resolved_target.kind == "agent_id":
            target_user_id = self._require_user_id_by_username(
                username=f"agent:{resolved_target.id}"
            )
            landed = self._find_or_create_direct_conversation(
                left_user_id=source_user_id,
                right_user_id=target_user_id,
                expected_direct_kind="agent-agent",
                caller_owner_id=caller_owner_id,
            )
            return DispatchResolution(
                resolved_target,
                landed.id,
                self.agent_node_id(agent_id=resolved_target.id),
            )
        target_user = self._users.get_user(user_id=resolved_target.id)
        if target_user is None:
            raise ValueError("user_id not found")
        landed = self._find_or_create_direct_conversation(
            left_user_id=source_user_id,
            right_user_id=target_user.id,
            expected_direct_kind="user-agent",
            caller_owner_id=caller_owner_id,
        )
        return DispatchResolution(resolved_target, landed.id, None)

    def resolve_user_agent_conversation(
        self,
        *,
        agent_id: str,
        user_id: str,
        caller_owner_id: str,
    ) -> str:
        """Create/reuse the canonical owner-to-agent direct conversation.

        Args:
            agent_id: Agent receiving or producing the background delivery.
            user_id: Owner user retained as the conversation creator.
            caller_owner_id: Explicit owner policy supplied by the caller.

        Returns:
            Canonical conversation id for the user/agent pair.

        Raises:
            ValueError: When either participant is missing.

        Side Effects:
            May create one direct conversation with the owner user as creator.
        """
        if self._users.get_user(user_id=user_id) is None:
            raise ValueError("user_id not found")
        agent_user_id = self._require_user_id_by_username(username=f"agent:{agent_id}")
        landed = self._find_or_create_direct_conversation(
            left_user_id=user_id,
            right_user_id=agent_user_id,
            expected_direct_kind="user-agent",
            caller_owner_id=caller_owner_id,
        )
        return landed.id

    def find_dispatch(
        self, *, dispatch_request_key: str | None
    ) -> AgentDispatchRecord | None:
        """Return the first durable dispatch result for a request key, if any."""
        if dispatch_request_key is None:
            return None
        row = self._connection.execute(
            """
            SELECT dispatch_request_key, source_agent_id, target_kind, target_id,
                   conversation_id, message_id
            FROM agent_message_dispatch_log
            WHERE dispatch_request_key = ?
            """,
            (dispatch_request_key,),
        ).fetchone()
        if row is None:
            return None
        return AgentDispatchRecord(
            dispatch_request_key=str(row["dispatch_request_key"]),
            source_agent_id=str(row["source_agent_id"]),
            target_kind=str(row["target_kind"]),
            target_id=str(row["target_id"]),
            conversation_id=str(row["conversation_id"]),
            message_id=str(row["message_id"]),
        )

    def record_dispatch(self, record: AgentDispatchRecord) -> AgentDispatchRecord:
        """Persist a dispatch result with first-write-wins idempotency.

        Side Effects:
            Commits the first record for a request key. A competing replay keeps and
            returns the existing record without overwriting it.
        """
        self._connection.execute(
            """
            INSERT OR IGNORE INTO agent_message_dispatch_log(
                dispatch_request_key, source_agent_id, target_kind, target_id,
                conversation_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                record.dispatch_request_key,
                record.source_agent_id,
                record.target_kind,
                record.target_id,
                record.conversation_id,
                record.message_id,
            ),
        )
        self._connection.commit()
        stored = self.find_dispatch(dispatch_request_key=record.dispatch_request_key)
        assert stored is not None
        return stored

    def system_user_id(self) -> str:
        """Return the well-known system user id, creating it when absent."""
        system_user = self._users.get_user_by_username(username="system")
        if system_user is None:
            system_user = self._users.create_user(
                username="system", display_name="System"
            )
        return system_user.id

    def agent_node_id(self, *, agent_id: str) -> str | None:
        """Return an agent's target node id, or None when unbound/missing."""
        profile = self._profiles.get_profile(agent_id=agent_id)
        if profile is None:
            return None
        return profile.node_id

    def conversation_usage_scope(self, *, conversation_id: str) -> str | None:
        """Return the owner scope used to aggregate conversation usage."""
        conversation = self._conversations.get_conversation(
            conversation_id=conversation_id
        )
        return conversation.owner_id if conversation is not None else None

    def _classify_dispatch_target(self, *, target: str) -> DispatchTarget:
        normalized = target.strip()
        if not normalized:
            raise ValueError("target must be non-empty")
        for prefix, kind in (
            ("conversation:", "conversation_id"),
            ("conversation_id:", "conversation_id"),
            ("agent:", "agent_id"),
            ("agent_id:", "agent_id"),
            ("user:", "user_id"),
            ("user_id:", "user_id"),
        ):
            if normalized.startswith(prefix):
                resolved_id = normalized[len(prefix) :].strip()
                if not resolved_id:
                    raise ValueError("target id must be non-empty")
                return DispatchTarget(kind=kind, id=resolved_id)
        if self._conversations.exists(normalized):
            return DispatchTarget(kind="conversation_id", id=normalized)
        by_id = self._users.get_user(user_id=normalized)
        if by_id is not None:
            if by_id.username.startswith("agent:"):
                agent_id = by_id.username[len("agent:") :].strip()
                return DispatchTarget(kind="agent_id", id=agent_id or by_id.id)
            return DispatchTarget(kind="user_id", id=by_id.id)
        if self._users.get_user_by_username(username=f"agent:{normalized}") is not None:
            return DispatchTarget(kind="agent_id", id=normalized)
        raise ValueError("target not found")

    def _find_or_create_direct_conversation(
        self,
        *,
        left_user_id: str,
        right_user_id: str,
        expected_direct_kind: str,
        caller_owner_id: str | None,
    ):  # noqa: ANN202
        existing = self._find_canonical_direct_conversation(
            left_user_id=left_user_id,
            right_user_id=right_user_id,
            expected_direct_kind=expected_direct_kind,
        )
        if existing is not None:
            return existing
        return self._conversations.create_conversation(
            title=self._build_default_direct_conversation_title(
                left_user_id=left_user_id,
                right_user_id=right_user_id,
                expected_direct_kind=expected_direct_kind,
            ),
            participant_ids=[left_user_id, right_user_id],
            creator_id=left_user_id,
            caller_owner_id=caller_owner_id,
        )

    def _find_canonical_direct_conversation(
        self,
        *,
        left_user_id: str,
        right_user_id: str,
        expected_direct_kind: str,
    ):  # noqa: ANN202
        pair = {left_user_id, right_user_id}
        direct_candidates = [
            item
            for item in self._conversations.list_conversations()
            if item.type == "direct"
            and len(item.participant_ids) == 2
            and set(item.participant_ids) == pair
        ]
        kind_matches = [
            item
            for item in direct_candidates
            if item.direct_kind == expected_direct_kind
        ]
        candidates = kind_matches or direct_candidates
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.created_at, item.id))[0]

    def _build_default_direct_conversation_title(
        self,
        *,
        left_user_id: str,
        right_user_id: str,
        expected_direct_kind: str,
    ) -> str:
        left_user = self._users.get_user(user_id=left_user_id)
        right_user = self._users.get_user(user_id=right_user_id)
        if expected_direct_kind == "user-agent":
            for user in (left_user, right_user):
                if user is not None and user.username.startswith("agent:"):
                    return user.display_name or user.username[len("agent:") :]
        if right_user is not None:
            return right_user.display_name or right_user.username
        if left_user is not None:
            return left_user.display_name or left_user.username
        return "Direct conversation"

    def _require_user_id_by_username(self, *, username: str) -> str:
        user = self._users.get_user_by_username(username=username)
        if user is None:
            raise ValueError(f"username not found: {username}")
        return user.id
