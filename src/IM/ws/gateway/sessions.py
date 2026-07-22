from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

from IM.api.ws.event_types import (
    EVENT_AGENT_CHANNEL_STATUS_CHANGED,
    EVENT_AGENT_STATUS_CHANGED,
    EVENT_NODE_STATUS_CHANGED,
    build_agent_channel_status_changed_payload,
    build_agent_status_changed_payload,
    build_node_status_changed_payload,
)
from IM.domain.models import NodeStatus
from IM.infra.gateway_persistence import GatewayNodePersistence
from IM.ws.user_stream import UserStreamRegistry
from .protocol import (
    _encode_status_frame,
    _normalize_agent_string_list_seed,
    _not_registered_error,
    _optional_int,
    _optional_text,
    _require_dict,
    _require_string_list,
    _require_text,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GatewayConnection:
    """Represent one active gateway websocket bound to a node id."""

    node_id: str
    owner_id: str
    websocket: WebSocket
    agents: list[str]
    capabilities: dict[str, object]
    reports: list[dict[str, object]]
    heartbeats: list[dict[str, object]]
    credential_key_id: str | None = None
    credential_algorithm: str | None = None
    credential_public_key: str | None = None


class GatewayAuthorizationError(PermissionError):
    """Reject an authenticated Gateway operation outside its owner scope."""

    code = "gateway_owner_mismatch"


class GatewaySessions:
    """Own active sockets, authorization, replacement, and status publication."""

    def __init__(
        self,
        *,
        node_persistence: GatewayNodePersistence | None = None,
        user_stream_registry: UserStreamRegistry | None = None,
        lock: asyncio.Lock | None = None,
    ) -> None:
        self._node_persistence = node_persistence
        self._user_stream_registry = user_stream_registry
        self._lock = lock or asyncio.Lock()
        self._status_seq_by_owner: dict[str, int] = {}
        self._status_seq_lock = asyncio.Lock()
        self._connections: dict[str, GatewayConnection] = {}

    async def disconnect(
        self,
        *,
        node_id: str,
        expected_websocket: WebSocket | None = None,
    ) -> None:
        """Remove one active node connection and broadcast offline if needed.

        Args:
            node_id: Node whose active connection should be removed.
            expected_websocket: When provided, remove the mapping only if it still
                belongs to this websocket. This prevents delayed cleanup from an old
                connection from deleting a newer registration for the same node.
        """
        async with self._lock:
            current = self._connections.get(node_id)
            if expected_websocket is not None and (
                current is None or current.websocket is not expected_websocket
            ):
                return
            self._connections.pop(node_id, None)
        if self._node_persistence is None:
            return
        transition = self._node_persistence.mark_offline(node_id=node_id)
        prior = transition.previous_node
        next_node = transition.current_node
        if (
            prior is not None
            and next_node is not None
            and prior.status != next_node.status
        ):
            await self._broadcast_status_change(
                owner_id=next_node.owner_id,
                node=next_node,
                agent_ids=list(transition.agent_ids),
            )

    async def force_mark_offline(self, *, node_id: str, reason: str) -> None:
        """Flip a stale node to offline (called by the heartbeat-timeout guard task).

        Args:
            node_id: Identifier of the node whose last heartbeat is past the timeout.
            reason: Diagnostic tag stored as ``last_error`` to surface why it flipped.

        Notes:
            Idempotent — if the node is already offline, its persisted state and
            existing ``last_error`` remain unchanged. The active in-memory
            ``self._connections`` entry is dropped before persistence, matching the
            WS-disconnect path semantics.
        """
        if self._node_persistence is None:
            return
        async with self._lock:
            self._connections.pop(node_id, None)
        transition = self._node_persistence.mark_offline(
            node_id=node_id, last_error=reason
        )
        prior = transition.previous_node
        if prior is None or prior.status == "offline":
            return
        next_node = transition.current_node
        if next_node is not None and prior.status != next_node.status:
            await self._broadcast_status_change(
                owner_id=next_node.owner_id,
                node=next_node,
                agent_ids=list(transition.agent_ids),
            )

    async def _next_status_seq(self, *, owner_id: str) -> int:
        """Allocate one monotonically increasing seq number per owner."""
        async with self._status_seq_lock:
            current = self._status_seq_by_owner.get(owner_id, 0) + 1
            self._status_seq_by_owner[owner_id] = current
            return current

    async def _broadcast_status_change(
        self,
        *,
        owner_id: str,
        node: NodeStatus,
        agent_ids: list[str],
    ) -> None:
        """Push one node.status_changed (+ per-agent agent.status_changed) frame to owner WS."""
        if self._user_stream_registry is None:
            return
        if not owner_id or not owner_id.strip():
            return  # orphan node — no audience.
        node_seq = await self._next_status_seq(owner_id=owner_id)
        node_payload = build_node_status_changed_payload(
            seq=node_seq,
            node_id=node.node_id,
            status=node.status,
            last_heartbeat_at=node.last_heartbeat_at,
            last_error=node.last_error,
        )
        await self._user_stream_registry.broadcast_to_user(
            owner_id,
            _encode_status_frame(
                event_type=EVENT_NODE_STATUS_CHANGED, payload=node_payload
            ),
        )
        for agent_id in agent_ids:
            agent_seq = await self._next_status_seq(owner_id=owner_id)
            agent_payload = build_agent_status_changed_payload(
                seq=agent_seq,
                agent_id=agent_id,
                status=node.status,
            )
            await self._user_stream_registry.broadcast_to_user(
                owner_id,
                _encode_status_frame(
                    event_type=EVENT_AGENT_STATUS_CHANGED, payload=agent_payload
                ),
            )

    async def broadcast_channel_status_change(
        self, *, owner_id: str, agent_id: str, channel_id: str
    ) -> None:
        """Invalidate only the authenticated owner's affected Agent channel list."""
        if self._user_stream_registry is None or not owner_id.strip():
            return
        seq = await self._next_status_seq(owner_id=owner_id)
        payload = build_agent_channel_status_changed_payload(
            seq=seq,
            agent_id=agent_id,
            channel_id=channel_id,
        )
        await self._user_stream_registry.broadcast_to_user(
            owner_id,
            _encode_status_frame(
                event_type=EVENT_AGENT_CHANNEL_STATUS_CHANGED,
                payload=payload,
            ),
        )

    async def is_connected(self, *, node_id: str) -> bool:
        """Report whether one node currently has an active websocket."""
        async with self._lock:
            return node_id in self._connections

    async def snapshot_connection(self, *, node_id: str) -> GatewayConnection | None:
        """Return one tracked connection snapshot for tests and diagnostics."""
        async with self._lock:
            return self._connections.get(node_id)

    async def list_connected_node_ids(self) -> set[str]:
        """Return all currently connected node identifiers."""
        async with self._lock:
            return set(self._connections.keys())

    async def register(
        self,
        *,
        websocket: WebSocket,
        payload: dict[str, object],
        authenticated_owner_id: str,
    ) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            registered_node_ids = [
                registered_node_id
                for registered_node_id, connection in self._connections.items()
                if connection.websocket is websocket
            ]
        if registered_node_ids and registered_node_ids != [node_id]:
            raise GatewayAuthorizationError(
                "gateway websocket is already registered to another node"
            )
        if self._node_persistence is not None:
            durable_owner = self._node_persistence.owner_for_node(node_id=node_id)
            if durable_owner and durable_owner != authenticated_owner_id:
                raise GatewayAuthorizationError("node is bound to another owner")
        agents = _require_string_list(payload.get("agents", []), field_name="agents")
        # bugfix-404-M2 decision 3: optional field carrying per-agent workspace seeds.
        # Old gateway frames omit this field; IM falls back to managed_workspace_root.
        raw_workspaces = payload.get("agent_workspaces")
        agent_workspaces: dict[str, str] = (
            {
                k: v
                for k, v in raw_workspaces.items()
                if isinstance(k, str) and isinstance(v, str)
            }
            if isinstance(raw_workspaces, dict)
            else {}
        )
        # bugfix-467: optional per-agent skills/tool_allowlist seeds.  Older gateways
        # omit these fields; IM creates an empty-shell profile as before.
        raw_skills = payload.get("agent_skills")
        agent_skills: dict[str, list[str]] = (
            _normalize_agent_string_list_seed(raw_skills)
            if isinstance(raw_skills, dict)
            else {}
        )
        raw_tools = payload.get("agent_tool_allowlist")
        agent_tool_allowlist: dict[str, list[str]] = (
            _normalize_agent_string_list_seed(raw_tools)
            if isinstance(raw_tools, dict)
            else {}
        )
        cap_raw = payload.get("capabilities")
        if cap_raw is None:
            capabilities: dict[str, object] = {}
        else:
            capabilities = _require_dict(cap_raw, field_name="capabilities")
        node_name = _optional_text(payload.get("node_name")) or node_id
        version = _optional_text(payload.get("version")) or ""
        connection = GatewayConnection(
            node_id=node_id,
            owner_id=authenticated_owner_id,
            websocket=websocket,
            agents=agents,
            capabilities=capabilities,
            reports=[],
            heartbeats=[],
            credential_key_id=_optional_text(payload.get("credential_key_id")),
            credential_algorithm=_optional_text(payload.get("credential_algorithm")),
            credential_public_key=_optional_text(payload.get("credential_public_key")),
        )
        async with self._lock:
            self._connections[node_id] = connection
        if self._node_persistence is not None:
            result = self._node_persistence.register(
                node_id=node_id,
                node_name=node_name,
                version=version,
                agent_ids=agents,
                agent_workspaces=agent_workspaces,
                agent_skills=agent_skills,
                agent_tool_allowlist=agent_tool_allowlist,
            )
            prior_status = (
                result.previous_node.status
                if result.previous_node is not None
                else None
            )
            if prior_status != result.current_node.status:
                await self._broadcast_status_change(
                    owner_id=result.current_node.owner_id,
                    node=result.current_node,
                    agent_ids=list(result.agent_ids),
                )
        return {
            "type": "ack",
            "payload": {"message_type": "node.register", "node_id": node_id},
        }

    async def authorize(
        self,
        *,
        websocket: WebSocket,
        payload: dict[str, object],
        authenticated_owner_id: str,
    ) -> GatewayConnection:
        """Bind every upstream business frame to its authenticated live socket.

        The websocket registration is the routing authority. Payload ``node_id`` is
        only an assertion and may never select a different connection. The dispatch
        boundary validates that assertion before this method normalizes the payload
        for downstream handlers.
        """
        async with self._lock:
            matches = [
                connection
                for connection in self._connections.values()
                if connection.websocket is websocket
            ]
        if len(matches) != 1:
            raise GatewayAuthorizationError(
                "gateway websocket is not registered to exactly one node"
            )
        connection = matches[0]
        if connection.owner_id != authenticated_owner_id:
            raise GatewayAuthorizationError(
                "gateway token owner does not match the registered connection"
            )
        payload_node_id = _optional_text(payload.get("node_id"))
        if payload_node_id and payload_node_id != connection.node_id:
            raise GatewayAuthorizationError(
                "payload node does not match the registered connection"
            )
        durable_owner = (
            self._node_persistence.owner_for_node(node_id=connection.node_id)
            if self._node_persistence is not None
            else ""
        )
        if durable_owner and durable_owner != connection.owner_id:
            raise GatewayAuthorizationError(
                "durable node owner does not match the registered connection"
            )
        payload["node_id"] = connection.node_id
        return connection

    async def heartbeat(self, *, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.heartbeats.append(payload)
        # bugfix-417-M3 R4: the node-heartbeat no longer refreshes a permission-specific
        # liveness marker. Permission waits now stay alive via the kernel run_heartbeat
        # that EventBridge persists as a conversation_events row (advancing last_evt), so
        # the relay watchdog needs no per-window exemption — one uniform liveness signal.
        if self._node_persistence is not None:
            transition = self._node_persistence.heartbeat(
                node_id=node_id,
                reported_status=_optional_text(payload.get("status")),
                agent_count=_optional_int(payload.get("agent_count")),
                last_error=_optional_text(payload.get("last_error")),
                version=_optional_text(payload.get("version")),
            )
            prior_status = (
                transition.previous_node.status
                if transition.previous_node is not None
                else None
            )
            next_node = transition.current_node
            if next_node is not None and prior_status != next_node.status:
                await self._broadcast_status_change(
                    owner_id=next_node.owner_id,
                    node=next_node,
                    agent_ids=list(transition.agent_ids),
                )
        return {
            "type": "ack",
            "payload": {"message_type": "node.heartbeat", "node_id": node_id},
        }

    async def send(
        self, *, target_node_id: str, message_type: str, payload: dict[str, object]
    ) -> bool:
        """Send one downstream frame and remove only its failing current socket."""
        async with self._lock:
            connection = self._connections.get(target_node_id)
        if connection is None:
            return False
        try:
            await connection.websocket.send_json(
                {"type": message_type, "payload": payload}
            )
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect(
                node_id=target_node_id, expected_websocket=connection.websocket
            )
            return False
        return True

    async def is_registered_sender(self, *, websocket: WebSocket, node_id: str) -> bool:
        async with self._lock:
            connection = self._connections.get(node_id)
            return connection is not None and connection.websocket is websocket
