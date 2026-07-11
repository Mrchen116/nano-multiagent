"""Concrete SQLite persistence operations for Gateway protocol workflows."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from IM.domain.models import NodeStatus, managed_workspace_root
from IM.infra.repositories import (
    AgentProfileRepository,
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
