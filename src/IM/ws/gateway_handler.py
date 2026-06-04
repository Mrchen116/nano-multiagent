"""Gateway WebSocket connection manager (see docs/specs/im/spec.md)."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

_logger = logging.getLogger(__name__)

from fastapi import WebSocket, WebSocketDisconnect

from IM.api.ws.event_types import (
    EVENT_AGENT_STATUS_CHANGED,
    EVENT_NODE_STATUS_CHANGED,
    build_agent_status_changed_payload,
    build_node_status_changed_payload,
)
from IM.application.event_bridge import EventBridge
from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from collections.abc import Callable

from IM.domain.models import (
    Actor,
    ConversationEvent,
    Message,
    NodeStatus,
    TokenUsage,
    ToolCall,
    managed_workspace_root,
)
from IM.infra.repositories import (
    AgentProfileRepository,
    ConversationRepository,
    EventRepository,
    MessageRepository,
    NodeRepository,
    UserRepository,
)
from IM.ws.user_stream import UserStreamRegistry


@dataclass(frozen=True, slots=True)
class GatewayConnection:
    """Represent one active gateway websocket bound to a node id."""

    node_id: str
    websocket: WebSocket
    agents: list[str]
    capabilities: dict[str, object]
    reports: list[dict[str, object]]
    heartbeats: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class DispatchTarget:
    """Represent one normalized outbound dispatch target."""

    kind: str
    id: str


class GatewayHandler:
    """Manage gateway websocket sessions and IM relay protocol messages.

    Args:
        relay_service: Relay task service used to update dispatch and receipt state.

    Notes:
        All in-memory connection maps are protected by a single asyncio lock because
        tests and app code share one process and only need correctness, not sharded
        concurrent throughput.
    """

    def __init__(
        self,
        *,
        relay_service: RelayService,
        node_repository: NodeRepository | None = None,
        event_repository: EventRepository | None = None,
        metrics_service: MetricsService | None = None,
        conversation_repository: ConversationRepository | None = None,
        user_event_notify: Callable[[ConversationEvent], None] | None = None,
        user_stream_registry: UserStreamRegistry | None = None,
        event_bridge: EventBridge | None = None,
    ) -> None:
        self._relay_service = relay_service
        self._node_repository = node_repository
        self._event_repository = event_repository
        self._metrics_service = metrics_service
        self._conversation_repository = conversation_repository
        self._user_repository = (
            UserRepository(conversation_repository._connection)
            if conversation_repository is not None
            else None
        )
        self._message_repository = (
            MessageRepository(
                conversation_repository._connection, notify=user_event_notify
            )
            if conversation_repository is not None
            else None
        )
        self._user_stream_registry = user_stream_registry
        # EventBridge wires kernel events → IM WS streaming events (feat-340-M14).
        # External injection takes priority (tests / explicit wiring); auto-build from repos as fallback.
        if event_bridge is not None:
            self._event_bridge: EventBridge | None = event_bridge
        elif (
            self._message_repository is not None and self._event_repository is not None
        ):
            self._event_bridge = EventBridge(
                message_repository=self._message_repository,
                event_repository=self._event_repository,
            )
        else:
            self._event_bridge = None
        self._status_seq_by_owner: dict[str, int] = {}
        self._status_seq_lock = asyncio.Lock()
        self._lock = asyncio.Lock()
        self._agent_message_lock = asyncio.Lock()
        self._connections: dict[str, GatewayConnection] = {}
        self._reports: list[dict[str, object]] = []
        self._agent_config_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        self._agent_create_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        self._agent_capabilities_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        self._node_capabilities_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        # feat-379-M2 R5: prompt-preview request→response futures
        self._prompt_preview_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        # feat-379-M9 (決策 11): node-level prompt-preview — no per-agent workspace needed
        self._node_prompt_preview_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        self._ensure_agent_message_dispatch_table()

    async def serve(self, websocket: WebSocket) -> None:
        """Accept one websocket and process gateway protocol frames until disconnect."""
        await websocket.accept()
        node_id: str | None = None
        try:
            while True:
                raw_message = await websocket.receive_text()
                payload = _decode_message(raw_message)
                message_type = _require_message_type(payload)
                body = _require_dict(payload.get("payload"), field_name="payload")
                response = await self.handle_message(
                    websocket=websocket,
                    message_type=message_type,
                    payload=body,
                )
                if response is not None:
                    await websocket.send_json(response)
                if message_type == "node.register":
                    node_id = str(body["node_id"])
        except WebSocketDisconnect:
            pass
        finally:
            if node_id is not None:
                await self.disconnect(node_id=node_id)

    async def handle_message(
        self,
        *,
        websocket: WebSocket,
        message_type: str,
        payload: dict[str, object],
    ) -> dict[str, object] | None:
        """Handle one gateway->IM protocol message and return optional ack/error."""
        if message_type == "node.register":
            return await self._handle_register(websocket=websocket, payload=payload)
        if message_type == "node.heartbeat":
            return await self._handle_heartbeat(payload=payload)
        if message_type == "node.report":
            return await self._handle_report(payload=payload)
        if message_type == "node.delivery_receipt":
            return await self._handle_delivery_receipt(payload=payload)
        if message_type == "agent.config":
            return await self._handle_agent_config(payload=payload)
        if message_type == "agent.created":
            return await self._handle_agent_created(payload=payload)
        if message_type == "agent.capabilities":
            return await self._handle_agent_capabilities(payload=payload)
        if message_type == "node.capabilities":
            return await self._handle_node_capabilities(payload=payload)
        if message_type == "agent.prompt.preview":
            return await self._handle_prompt_preview(payload=payload)
        if message_type == "node.prompt.preview":
            return await self._handle_node_prompt_preview(payload=payload)
        if message_type == "agent.message":
            return await self._handle_agent_message(payload=payload)
        if message_type == "node.streaming_delta":
            return await self._handle_streaming_delta(payload=payload)
        if message_type == "node.system_message":
            return await self._handle_system_message(payload=payload)
        return {
            "type": "error",
            "payload": {"code": "unsupported_message_type", "message": message_type},
        }

    async def push_relay_message(
        self, *, relay_task_id: str, target_node_id: str, payload: dict[str, object]
    ) -> bool:
        """Push one relay.message frame to a connected gateway node.

        Returns:
            True when a connected node received the frame, otherwise False.
        """
        async with self._lock:
            connection = self._connections.get(target_node_id)
        if connection is None:
            return False
        try:
            await connection.websocket.send_json(
                {
                    "type": "relay.message",
                    "payload": {**payload, "relay_task_id": relay_task_id},
                }
            )
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect(node_id=target_node_id)
            return False
        self._relay_service.mark_dispatched(relay_task_id=relay_task_id)
        return True

    async def push_config_sync(
        self, *, target_node_id: str, agent_id: str, profile_version: int
    ) -> bool:
        """Push one config.sync notification to a connected gateway node."""
        return await self._push_downstream(
            target_node_id=target_node_id,
            message_type="config.sync",
            payload={"agent_id": agent_id, "profile_version": profile_version},
        )

    async def push_heartbeat_trigger(
        self, *, target_node_id: str, agent_id: str, reason: str
    ) -> bool:
        """Push one heartbeat.trigger notification to a connected gateway node."""
        return await self._push_downstream(
            target_node_id=target_node_id,
            message_type="heartbeat.trigger",
            payload={"agent_id": agent_id, "reason": reason},
        )

    async def push_permission_response(
        self,
        *,
        target_node_id: str,
        message_id: str,
        request_id: str,
        decision: str,
    ) -> bool:
        """Push a permission_response frame to the gateway node hosting the parked run.

        The PA side consumes this frame and forwards the decision to the agent inbound
        endpoint so the parked hook can resume.

        Args:
            target_node_id: Node that owns the agent run awaiting the decision.
            message_id: Agent message that embeds the permission request.
            request_id: Stable permission request identifier.
            decision: User-chosen option (e.g. ``"allow_once"``, ``"deny"``).

        Returns:
            ``True`` when the node was connected and the frame was sent.
        """
        return await self._push_downstream(
            target_node_id=target_node_id,
            message_type="node.streaming_delta",
            payload={
                "kind": "permission_response",
                "message_id": message_id,
                "request_id": request_id,
                "decision": decision,
            },
        )

    async def request_agent_config(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Request one live agent config snapshot from a connected gateway node."""
        request_id = f"agent-config-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_config_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="agent.config.get",
                payload={"request_id": request_id, "agent_id": agent_id},
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_config_waiters.pop(request_id, None)

    async def request_agent_create(
        self,
        *,
        target_node_id: str,
        payload: dict[str, object],
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Request one gateway node to create an agent and return its created agent payload."""
        request_id = f"agent-create-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_create_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="agent.create",
                payload={"request_id": request_id, "agent": dict(payload)},
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_create_waiters.pop(request_id, None)

    async def request_agent_capabilities(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Request one gateway node to resolve runtime capabilities for an agent workspace."""
        request_id = f"agent-capabilities-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_capabilities_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="agent.capabilities.resolve",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_capabilities_waiters.pop(request_id, None)

    async def request_node_capabilities(
        self,
        *,
        target_node_id: str,
        timeout_seconds: float = 15.0,
    ) -> dict[str, object] | None:
        """请求网关节点当场解析 models/skills/tools 等（不从 IM 数据库读取）。"""
        request_id = f"node-capabilities-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._node_capabilities_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="node.capabilities.resolve",
                payload={"request_id": request_id},
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._node_capabilities_waiters.pop(request_id, None)

    async def request_prompt_preview(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        features: dict[str, bool],
        custom_prompt: str | None,
        tool_ids: list[str],
        scenario: str,
        skill_ids: list[str] | None = None,
        timeout_seconds: float = 10.0,
        heartbeat_enabled: bool | None = None,
        cron_enabled: bool | None = None,
    ) -> dict[str, object] | None:
        """Send an agent.prompt.preview.request frame and await the assembled result.

        feat-379-M2 R5: IM proxy path — IM sends this request to the Gateway
        which calls agent HTTP /v1/prompt-preview and returns the result.
        feat-383-M1: skill_ids forwarded so Gateway→kernel can resolve real skills.
        feat-394-M4 R2-2: heartbeat_enabled/cron_enabled forwarded so preview
        correctly reflects the agent's heartbeat/cron toggle state.

        Returns:
            Preview payload dict or None when the node is not connected or times out.
        """
        request_id = f"prompt-preview-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._prompt_preview_waiters[request_id] = waiter
        payload: dict[str, object] = {
            "request_id": request_id,
            "agent_id": agent_id,
            "workspace_root": workspace_root,
            "features": features,
            "custom_prompt": custom_prompt,
            "tool_ids": tool_ids,
            "skill_ids": skill_ids or [],
            "scenario": scenario,
        }
        # feat-394-M4 R2-2: include heartbeat/cron flags only when provided so
        # the gateway-side handler can forward them to assemble_prompt_preview.
        if heartbeat_enabled is not None:
            payload["heartbeat_enabled"] = heartbeat_enabled
        if cron_enabled is not None:
            payload["cron_enabled"] = cron_enabled
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="agent.prompt.preview.request",
                payload=payload,
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._prompt_preview_waiters.pop(request_id, None)

    async def request_node_prompt_preview(
        self,
        *,
        target_node_id: str,
        features: dict[str, bool],
        custom_prompt: str | None,
        tool_ids: list[str],
        scenario: str,
        workspace_root: str = "",
        skill_ids: list[str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object] | None:
        """Send a node.prompt.preview.request frame and await the assembled result.

        feat-379-M9 (決策 11): node-level preview path used by the agent-create page
        before an agent exists.
        feat-383-M1: workspace_root (IM-derived) and skill_ids are now forwarded so
        the Gateway→kernel can resolve real workspace and skills.

        Returns:
            Preview payload dict or None when the node is not connected or times out.
        """
        request_id = f"node-prompt-preview-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._node_prompt_preview_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="node.prompt.preview.request",
                payload={
                    "request_id": request_id,
                    "workspace_root": workspace_root,
                    "features": features,
                    "custom_prompt": custom_prompt,
                    "tool_ids": tool_ids,
                    "skill_ids": skill_ids or [],
                    "scenario": scenario,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._node_prompt_preview_waiters.pop(request_id, None)

    async def disconnect(self, *, node_id: str) -> None:
        """Remove one node from the active connection map and broadcast offline if needed."""
        async with self._lock:
            self._connections.pop(node_id, None)
        if self._node_repository is None:
            return
        prior = self._node_repository.get_node(node_id=node_id)
        agent_ids = self._list_node_agent_ids(node_id=node_id)
        self._node_repository.mark_disconnected(node_id=node_id)
        next_node = self._node_repository.get_node(node_id=node_id)
        if (
            prior is not None
            and next_node is not None
            and prior.status != next_node.status
        ):
            await self._broadcast_status_change(
                owner_id=next_node.owner_id,
                node=next_node,
                agent_ids=agent_ids,
            )

    async def force_mark_offline(self, *, node_id: str, reason: str) -> None:
        """Flip a stale node to offline (called by the heartbeat-timeout guard task).

        Args:
            node_id: Identifier of the node whose last heartbeat is past the timeout.
            reason: Diagnostic tag stored as ``last_error`` to surface why it flipped.

        Notes:
            Idempotent — if the node is already offline, this is a no-op aside from
            persisting ``last_error``. The active in-memory ``self._connections``
            entry is also dropped, matching the WS-disconnect path semantics.
        """
        if self._node_repository is None:
            return
        prior = self._node_repository.get_node(node_id=node_id)
        if prior is None or prior.status == "offline":
            return
        agent_ids = self._list_node_agent_ids(node_id=node_id)
        async with self._lock:
            self._connections.pop(node_id, None)
        # Record last_error then flip to offline. mark_disconnected handles status flip;
        # write last_error via a heartbeat-style update so it surfaces in /im/v1/nodes.
        self._node_repository._connection.execute(  # noqa: SLF001
            "UPDATE nodes SET last_error = ? WHERE node_id = ?",
            (reason, node_id),
        )
        self._node_repository._connection.commit()  # noqa: SLF001
        self._node_repository.mark_disconnected(node_id=node_id)
        next_node = self._node_repository.get_node(node_id=node_id)
        if next_node is not None and prior.status != next_node.status:
            await self._broadcast_status_change(
                owner_id=next_node.owner_id,
                node=next_node,
                agent_ids=agent_ids,
            )

    def _list_node_agent_ids(self, *, node_id: str) -> list[str]:
        """Return agent ids currently advertised by the given node, in stable order."""
        if self._node_repository is None:
            return []
        rows = self._node_repository._connection.execute(  # noqa: SLF001
            "SELECT agent_id FROM agent_profiles WHERE node_id = ? ORDER BY agent_id",
            (node_id,),
        ).fetchall()
        return [str(row["agent_id"]) for row in rows]

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

    async def _handle_register(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        agents = _require_string_list(payload.get("agents", []), field_name="agents")
        cap_raw = payload.get("capabilities")
        if cap_raw is None:
            capabilities: dict[str, object] = {}
        else:
            capabilities = _require_dict(cap_raw, field_name="capabilities")
        node_name = _optional_text(payload.get("node_name")) or node_id
        version = _optional_text(payload.get("version")) or ""
        connection = GatewayConnection(
            node_id=node_id,
            websocket=websocket,
            agents=agents,
            capabilities=capabilities,
            reports=[],
            heartbeats=[],
        )
        async with self._lock:
            self._connections[node_id] = connection
        prior_node: NodeStatus | None = None
        if self._node_repository is not None:
            prior_node = self._node_repository.get_node(node_id=node_id)
            node = self._node_repository.record_gateway_registration(
                node_id=node_id,
                node_name=node_name,
                version=version,
                agent_count=len(agents),
            )
            profile_repository = AgentProfileRepository(
                self._node_repository._connection
            )
            for agent_id in agents:
                existing = profile_repository.get_profile(agent_id=agent_id)
                owner_id = (
                    existing.owner_id
                    if existing is not None and existing.owner_id.strip()
                    else (node.owner_id or "")
                )
                if existing is None:
                    runtime_display_name = agent_id
                    runtime_description = f"Runtime agent advertised by {node_name}."
                    runtime_system_prompt = f"You are {agent_id}."
                    runtime_skills: list[str] = []
                    runtime_tool_allowlist: list[str] = []
                    runtime_group_reply_policy = "MENTION"
                    runtime_default_model: str | None = None
                    runtime_workspace_root = managed_workspace_root(agent_id)
                else:
                    runtime_display_name = existing.display_name
                    runtime_description = existing.description
                    runtime_system_prompt = existing.system_prompt
                    runtime_skills = existing.skills
                    runtime_tool_allowlist = existing.tool_allowlist
                    runtime_group_reply_policy = existing.group_reply_policy
                    runtime_default_model = existing.default_model
                    runtime_workspace_root = (
                        existing.workspace_root or managed_workspace_root(agent_id)
                    )
                if runtime_display_name == agent_id and agent_id.startswith("agent-"):
                    runtime_display_name = (
                        agent_id.replace("agent-", "", 1).replace("-", " ").title()
                    )
                # feat-379-M6 (ISSUE-2): preserve features/custom_prompt from the existing
                # DB row when re-registering. node.register only carries agent_ids, not
                # per-agent config, so passing None would overwrite user edits with defaults.
                runtime_features = existing.features if existing is not None else None
                runtime_custom_prompt = (
                    existing.custom_prompt if existing is not None else None
                )
                profile_repository.upsert_profile(
                    agent_id=agent_id,
                    owner_id=owner_id,
                    display_name=runtime_display_name,
                    description=runtime_description,
                    system_prompt=runtime_system_prompt,
                    skills=runtime_skills,
                    tool_allowlist=runtime_tool_allowlist,
                    group_reply_policy=runtime_group_reply_policy,
                    default_model=runtime_default_model,
                    workspace_root=runtime_workspace_root,
                    features=runtime_features,
                    custom_prompt=runtime_custom_prompt,
                )
                self._node_repository._connection.execute(
                    "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
                    (node_id, agent_id),
                )
            profile_repository.mark_stale_for_node(
                node_id=node_id,
                advertised_agent_ids=list(agents),
            )
            self._node_repository._connection.commit()
            prior_status = prior_node.status if prior_node is not None else None
            if prior_status != node.status:
                await self._broadcast_status_change(
                    owner_id=node.owner_id,
                    node=node,
                    agent_ids=list(agents),
                )
        return {
            "type": "ack",
            "payload": {"message_type": "node.register", "node_id": node_id},
        }

    async def _handle_heartbeat(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.heartbeats.append(payload)
        if self._node_repository is not None:
            prior_node = self._node_repository.get_node(node_id=node_id)
            next_node = self._node_repository.record_heartbeat(
                node_id=node_id,
                reported_status=_optional_text(payload.get("status")),
                agent_count=_optional_int(payload.get("agent_count")),
                last_error=_optional_text(payload.get("last_error")),
                version=_optional_text(payload.get("version")),
            )
            prior_status = prior_node.status if prior_node is not None else None
            if prior_status != next_node.status:
                await self._broadcast_status_change(
                    owner_id=next_node.owner_id,
                    node=next_node,
                    agent_ids=self._list_node_agent_ids(node_id=node_id),
                )
        return {
            "type": "ack",
            "payload": {"message_type": "node.heartbeat", "node_id": node_id},
        }

    async def _handle_report(self, *, payload: dict[str, object]) -> dict[str, object]:
        # Validate node_id first; a missing or empty node_id means the payload is structurally
        # invalid and we cannot even look up the connection. Return an error frame so the Gateway
        # knows the frame was rejected, but keep the WS connection alive.
        try:
            node_id = _require_text(payload.get("node_id"), field_name="node_id")
        except (RuntimeError, ValueError) as exc:
            return {
                "type": "error",
                "payload": {"code": "bad_payload", "message": str(exc)},
            }
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.reports.append(payload)
            self._reports.append(payload)
        # Persist errors (e.g. FK violations from synthetic conversation_id/message_id) must not
        # propagate out of the WS dispatch layer. A malformed heartbeat payload lacking real FK
        # rows in the messages table would raise sqlite3.IntegrityError here and close the
        # connection. The correct behaviour is to record the failure and return a normal ack
        # so the Gateway's connection stays alive.
        try:
            self._persist_report_event(payload=payload)
            self._persist_report_usage(payload=payload)
        except Exception as exc:  # noqa: BLE001
            # Non-fatal: persistence failed (likely FK violation from synthetic IDs).
            # Log via events so the failure is visible without severing the connection.
            _logger.warning(
                "node.report persist failed for node_id=%s: %s", node_id, exc
            )
        return {
            "type": "ack",
            "payload": {"message_type": "node.report", "node_id": node_id},
        }

    async def _handle_streaming_delta(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Translate gateway streaming events into IM WS fan-out via EventBridge.

        The gateway (personal_assistant) calls this with sub-types keyed by ``kind``:
        - ``turn_start``: agent begins a reply; EventBridge inserts placeholder message.
        - ``message_delta``: incremental text chunk; EventBridge appends content.
        - ``message_completed``: run finished; EventBridge marks message completed with token_usage.
        - ``tool_call_upserted``: tool call started; EventBridge upserts tool_calls JSON.
        - ``tool_call_completed``: tool call done; EventBridge settles tool_calls JSON.

        Cross-tenant isolation: every frame carries ``owner_id``; EventBridge → notify callback
        → build_notify_enqueue reads conversation_participants which already gates by owner.
        The broadcast_to_users path is never called here (streaming delta is owner-scoped only).
        """
        if self._event_bridge is None:
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta"}}

        kind = _optional_text(payload.get("kind")) or ""

        if kind == "turn_start":
            agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
            to_user_id = _optional_text(payload.get("to_user_id"))
            raw_conversation_id = _optional_text(payload.get("conversation_id"))

            if to_user_id is not None and raw_conversation_id is None:
                # feat-393: heartbeat/cron lazy-resolution mode.  Gateway sends to_user_id
                # (the owner) instead of conversation_id; we resolve/create the canonical
                # (owner, agent) direct conversation here, then fall through to the shared
                # on_turn_start path.  The ack returns both conversation_id and message_id
                # so the gateway can seed run_context_store with both values.
                #
                # Two modes are mutually exclusive: conversation_id → normal eager-bubble
                # path (unchanged); to_user_id → lazy canonical-conv resolution path.
                if (
                    self._conversation_repository is None
                    or self._user_repository is None
                ):
                    return {
                        "type": "ack",
                        "payload": {
                            "message_type": "node.streaming_delta",
                            "kind": kind,
                            "skipped": "repositories_not_configured",
                        },
                    }
                agent_user_id = _optional_text(payload.get("agent_user_id"))
                if agent_user_id is None:
                    row = self._user_repository._connection.execute(  # noqa: SLF001
                        "SELECT id FROM users WHERE username = ?",
                        (f"agent:{agent_id}",),
                    ).fetchone()
                    if row is None:
                        return {
                            "type": "ack",
                            "payload": {
                                "message_type": "node.streaming_delta",
                                "kind": kind,
                                "skipped": "agent_user_id_not_found",
                            },
                        }
                    agent_user_id = str(row["id"])
                # feat-393 fix-r1: owner lookup / canonical-conv creation can fail when
                # config.node.user_id is stale or the ephemeral IM DB has no such user yet.
                # Must NOT raise out of this handler — that would close the WS connection and
                # cause the Gateway to reconnect immediately, producing the 413-open/close flap
                # seen in round-1 acceptance (refactor-387 "坏帧关连接" pattern re-introduced).
                # Per design decision-6: delivery failure ≠ run failure; log and return skipped
                # ack so the Gateway can continue and this heartbeat run completes normally.
                try:
                    canonical_conv = self._find_or_create_direct_conversation(
                        left_user_id=to_user_id,
                        right_user_id=agent_user_id,
                        expected_direct_kind="user-agent",
                        # Pass the owner's own id as caller_owner_id so the created
                        # conversation is visible via list_conversations_for_owner.
                        # Without this, the conversation is created with the owner_id
                        # derived from the users table, which may be stale across e2e runs.
                        caller_owner_id=to_user_id,
                    )
                except (ValueError, Exception) as exc:  # noqa: BLE001
                    _logger.warning(
                        "turn_start to_user_id=%s owner_unresolved — skipping delivery: %s",
                        to_user_id,
                        exc,
                    )
                    return {
                        "type": "ack",
                        "payload": {
                            "message_type": "node.streaming_delta",
                            "kind": kind,
                            "skipped": "owner_unresolved",
                        },
                    }
                created_message = self._event_bridge.on_turn_start(
                    conversation_id=canonical_conv.id,
                    agent_user_id=agent_user_id,
                    agent_id=agent_id,
                )
                # Return both conversation_id and message_id so the gateway can update
                # run_context_store with the resolved canonical conversation (feat-393 design §接口与数据流).
                return {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.streaming_delta",
                        "kind": kind,
                        "conversation_id": canonical_conv.id,
                        "message_id": created_message.id,
                    },
                }

            # Normal path: conversation_id is provided (eager placeholder for regular chat).
            conversation_id = _require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            )
            # Resolve IM user ID from agent_id; gateway sends agent_id (e.g. "alpha"),
            # IM stores the agent as username="agent:<agent_id>" in the users table.
            agent_user_id = _optional_text(payload.get("agent_user_id"))
            if agent_user_id is None and self._user_repository is not None:
                row = self._user_repository._connection.execute(  # noqa: SLF001
                    "SELECT id FROM users WHERE username = ?",
                    (f"agent:{agent_id}",),
                ).fetchone()
                if row is not None:
                    agent_user_id = str(row["id"])
            if agent_user_id is None:
                return {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.streaming_delta",
                        "kind": kind,
                        "skipped": "agent_user_id_not_found",
                    },
                }
            created_message = self._event_bridge.on_turn_start(
                conversation_id=conversation_id,
                agent_user_id=agent_user_id,
                agent_id=agent_id,
            )
            # Return message_id in ack so PA observer can update run_context_store;
            # without this, observer keeps empty message_id and delta targets user message.
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": kind,
                    "message_id": created_message.id,
                },
            }

        elif kind == "message_delta":
            message_id = _require_text(
                payload.get("message_id"), field_name="message_id"
            )
            delta_text = _optional_text(payload.get("delta_text")) or ""
            self._event_bridge.on_message_delta(
                message_id=message_id, delta_text=delta_text
            )

        elif kind == "message_completed":
            message_id = _require_text(
                payload.get("message_id"), field_name="message_id"
            )
            final_content = _optional_text(payload.get("final_content"))
            token_usage = _parse_token_usage(payload.get("token_usage"))
            raw_ds = _optional_text(payload.get("delivery_status"))
            # bugfix-380: delivery_status is optional (back-compat: absent → "completed");
            # if provided it must be a known terminal value. Silent fallback was a
            # regression trap — any new failure semantic added upstream (e.g. "cancelled"
            # / "timeout") that wasn't whitelisted here would degrade back to the
            # bugfix-380 pre-fix bug: empty bubble silently marked "completed".
            if raw_ds is None:
                ds = "completed"
            elif raw_ds in {"completed", "failed"}:
                ds = raw_ds
            else:
                raise ValueError(
                    f"delivery_status must be 'completed' or 'failed' when provided, got {raw_ds!r}"
                )
            self._event_bridge.on_message_completed(
                message_id=message_id,
                final_content=final_content,
                token_usage=token_usage,
                delivery_status=ds,
            )

        elif kind == "tool_call_upserted":
            message_id = _require_text(
                payload.get("message_id"), field_name="message_id"
            )
            tc = _parse_tool_call(payload.get("tool_call"))
            self._event_bridge.on_tool_call_upserted(
                message_id=message_id, tool_call=tc
            )

        elif kind == "tool_call_completed":
            message_id = _require_text(
                payload.get("message_id"), field_name="message_id"
            )
            tc = _parse_tool_call(payload.get("tool_call"))
            self._event_bridge.on_tool_call_completed(
                message_id=message_id, tool_call=tc
            )

        elif kind == "permission_request":
            # PA → IM: agent is awaiting a user decision; EventBridge persists the pending
            # request and fans out permission.request to connected browser clients.
            message_id = _require_text(
                payload.get("message_id"), field_name="message_id"
            )
            permission_request = payload.get("permission_request")
            if not isinstance(permission_request, dict):
                raise ValueError("permission_request must be a dict")
            self._event_bridge.on_permission_request(
                message_id=message_id,
                permission_request=permission_request,
            )

        elif kind == "permission_resolved":
            # PA → IM: user's decision has been forwarded to the agent; update persisted
            # status and notify browser clients so the card can settle.
            message_id = _require_text(
                payload.get("message_id"), field_name="message_id"
            )
            request_id = _require_text(
                payload.get("request_id"), field_name="request_id"
            )
            decision = _require_text(payload.get("decision"), field_name="decision")
            self._event_bridge.on_permission_resolved(
                message_id=message_id,
                request_id=request_id,
                decision=decision,
            )

        elif kind == "permission_response":
            # IM → PA direction: user's decision is forwarded to the agent kernel.
            # Routing to the pending PA WS connection is handled elsewhere (REST endpoint
            # + GatewayHandler.send_to_node); streaming_delta is only PA→IM.
            pass

        return {
            "type": "ack",
            "payload": {"message_type": "node.streaming_delta", "kind": kind},
        }

    async def _handle_delivery_receipt(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        relay_task_id = _require_text(
            payload.get("relay_task_id"), field_name="relay_task_id"
        )
        delivery_status = _require_text(
            payload.get("delivery_status"), field_name="delivery_status"
        )
        detail = payload.get("detail")
        if detail is not None and not isinstance(detail, str):
            raise ValueError("detail must be a string when provided")
        async with self._lock:
            if node_id not in self._connections:
                return _not_registered_error(node_id=node_id)
        task = self._relay_service.apply_delivery_receipt(
            relay_task_id=relay_task_id,
            delivery_status=delivery_status,
            detail=detail,
        )
        self._persist_receipt_events(task=task, node_id=node_id, detail=detail)
        if delivery_status == "completed":
            await self._broadcast_group_reply_context(
                task=task, node_id=node_id, detail=detail
            )
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.delivery_receipt",
                "node_id": node_id,
                "relay_task_id": relay_task_id,
                "status": task.status,
            },
        }

    async def _broadcast_group_reply_context(
        self, *, task, node_id: str, detail: str | None
    ) -> None:  # noqa: ANN001
        if self._conversation_repository is None or self._user_repository is None:
            return
        if (
            detail is None
            or not detail.strip()
            or detail.strip() == "NO_REPLY"
            or "suppressed_by=no_reply_token" in detail
        ):
            return
        relay_metadata = task.payload.get("metadata", {})
        if (
            not isinstance(relay_metadata, dict)
            or relay_metadata.get("conversation_type") != "group"
        ):
            return
        source_agent_id = task.payload.get("agent_id")
        if not isinstance(source_agent_id, str) or not source_agent_id.strip():
            return
        conversation = self._conversation_repository.get_conversation(
            conversation_id=task.conversation_id
        )
        if conversation is None:
            return
        participant_ids = [
            item.user_id or item.id
            for item in conversation.participants
            if (item.user_id or item.id).strip()
        ] or conversation.participant_ids
        if not participant_ids:
            return
        placeholders = ",".join("?" for _ in participant_ids)
        participant_rows = self._conversation_repository._connection.execute(  # noqa: SLF001
            f"SELECT id, username, display_name FROM users WHERE id IN ({placeholders})",  # noqa: S608, SLF001
            tuple(participant_ids),
        ).fetchall()
        source_user = self._conversation_repository._connection.execute(  # noqa: SLF001
            "SELECT id, display_name FROM users WHERE username = ?",
            (f"agent:{source_agent_id}",),
        ).fetchone()
        if source_user is None:
            return
        sender_user_id = str(source_user["id"])
        sender_display_name = str(source_user["display_name"])
        peer_agent_ids: list[str] = []
        for row in participant_rows:
            username = str(row["username"])
            if not username.startswith("agent:"):
                continue
            agent_id = username[len("agent:") :].strip()
            if not agent_id or agent_id == source_agent_id:
                continue
            peer_agent_ids.append(agent_id)
        if not peer_agent_ids:
            return

        # bugfix-358: IM 在此处只做哑路由——给每个 peer agent 各扇出一份 group relay。
        # 是否触发回复(MENTION gate)的判断完全交给 Gateway:Gateway 看 enqueue_message_relay
        # 内部从 content 里 <mention type="agent" target_id="X"/> 标签解出的 mentioned_agent_ids,
        # 自己 in 列表 → 触发;否则 buffer 进 group_context_store 当背景上下文(inbound_pipeline §3.1)。
        # content 不在 IM 端预加 sender 前缀:Gateway pipeline 会按 _format_sender_text(sender_label, text)
        # 自己拼 [sender] 前缀;IM 再加一遍会 double-prefix。
        synthetic_message = Message(
            id=task.message_id,
            conversation_id=task.conversation_id,
            sender_user_id=sender_user_id,
            sender_type="agent",
            sender=Actor(
                type="agent",
                id=source_agent_id,
                display_name=sender_display_name,
                user_id=sender_user_id,
            ),
            content=detail.strip(),
            attachments=[],
            delivery_status="completed",
            created_at=task.updated_at,
        )
        for peer_agent_id in peer_agent_ids:
            profile_row = self._conversation_repository._connection.execute(  # noqa: SLF001
                "SELECT node_id FROM agent_profiles WHERE agent_id = ?",
                (peer_agent_id,),
            ).fetchone()
            if profile_row is None or profile_row["node_id"] is None:
                continue
            target_node_id = str(profile_row["node_id"])
            result = self._relay_service.enqueue_message_relay(
                message=synthetic_message,
                target_node_id=target_node_id,
                idempotency_key=f"agent-reply:{task.relay_task_id}:{peer_agent_id}",
                sender_user_id=sender_user_id,
                conversation_type="group",
                extra_metadata={
                    "source_agent_id": source_agent_id,
                    "sender_display_name": sender_display_name,
                },
                _override_agent_id=peer_agent_id,
            )
            if result.created:
                await self.push_relay_message(
                    relay_task_id=result.relay_task.relay_task_id,
                    target_node_id=target_node_id,
                    payload=result.relay_task.payload,
                )

    async def _push_downstream(
        self, *, target_node_id: str, message_type: str, payload: dict[str, object]
    ) -> bool:
        async with self._lock:
            connection = self._connections.get(target_node_id)
        if connection is None:
            return False
        try:
            await connection.websocket.send_json(
                {"type": message_type, "payload": payload}
            )
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect(node_id=target_node_id)
            return False
        return True

    async def _handle_agent_config(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
        agent_payload = payload.get("agent")
        if agent_payload is not None and not isinstance(agent_payload, dict):
            raise ValueError("agent must be an object when provided")
        async with self._lock:
            waiter = self._agent_config_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(
                dict(agent_payload) if isinstance(agent_payload, dict) else None
            )
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.config",
                "request_id": request_id,
                "agent_id": agent_id,
            },
        }

    async def _handle_agent_created(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        agent_payload = _require_dict(payload.get("agent"), field_name="agent")
        async with self._lock:
            waiter = self._agent_create_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(agent_payload))
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.created",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_agent_capabilities(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
        # Validate workspace_root is present even though this handler doesn't use it directly.
        _require_text(payload.get("workspace_root"), field_name="workspace_root")
        capabilities = _require_dict(
            payload.get("capabilities"), field_name="capabilities"
        )
        async with self._lock:
            waiter = self._agent_capabilities_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(capabilities))
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.capabilities",
                "request_id": request_id,
                "node_id": node_id,
                "agent_id": agent_id,
            },
        }

    async def _handle_node_capabilities(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        capabilities = _require_dict(
            payload.get("capabilities"), field_name="capabilities"
        )
        async with self._lock:
            waiter = self._node_capabilities_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(capabilities))
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.capabilities",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_prompt_preview(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve prompt-preview waiter when Gateway returns assembled preview text.

        feat-379-M2 R5: Gateway calls agent HTTP /v1/prompt-preview and sends
        ``agent.prompt.preview`` back with {request_id, node_id, preview}.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        preview = payload.get("preview")
        if not isinstance(preview, dict):
            preview = {}
        async with self._lock:
            waiter = self._prompt_preview_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(preview))
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.prompt.preview",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_node_prompt_preview(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve node-level prompt-preview waiter when Gateway returns assembled preview.

        feat-379-M9 (決策 11): Gateway sends ``node.prompt.preview`` in response to
        ``node.prompt.preview.request``.  No per-agent context is required.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        preview = payload.get("preview")
        if not isinstance(preview, dict):
            preview = {}
        async with self._lock:
            waiter = self._node_prompt_preview_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(preview))
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.prompt.preview",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_agent_message(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist one gateway-dispatched send_message payload into IM conversations."""
        if (
            self._conversation_repository is None
            or self._user_repository is None
            or self._message_repository is None
        ):
            return {
                "type": "error",
                "payload": {
                    "code": "gateway_not_configured",
                    "message": "conversation_repository and user_repository must be configured",
                },
            }

        try:
            text = _require_text(payload.get("text"), field_name="text").strip()
            target = _require_text(payload.get("to"), field_name="to").strip()
            source_raw = _require_text(
                payload.get("from_session_id"), field_name="from_session_id"
            ).strip()
            source_agent_id, dispatch_request_id = (
                self._resolve_dispatch_source_from_session_id(source_raw=source_raw)
            )
            resolved_target, conversation_id = self.resolve_send_message_target(
                source_agent_id=source_agent_id,
                target=target,
            )
            dispatch_request_key = (
                f"{source_agent_id}:{dispatch_request_id}"
                if dispatch_request_id is not None
                else None
            )
            existing = (
                self._find_dispatched_agent_message(
                    dispatch_request_key=dispatch_request_key
                )
                if dispatch_request_key is not None
                else None
            )
            if existing is None:
                async with self._agent_message_lock:
                    existing = (
                        self._find_dispatched_agent_message(
                            dispatch_request_key=dispatch_request_key
                        )
                        if dispatch_request_key is not None
                        else None
                    )
                    if existing is None:
                        sender_user_id = self._require_user_id_by_username(
                            username=f"agent:{source_agent_id}"
                        )
                        message = self._message_repository.create_message(
                            conversation_id=conversation_id,
                            sender_user_id=sender_user_id,
                            sender_type="agent",
                            content=text,
                        )
                        if dispatch_request_key is not None:
                            self._record_dispatched_agent_message(
                                dispatch_request_key=dispatch_request_key,
                                source_agent_id=source_agent_id,
                                target_kind=resolved_target.kind,
                                target_id=resolved_target.id,
                                conversation_id=conversation_id,
                                message_id=message.id,
                            )
                        if (
                            resolved_target.kind == "agent_id"
                            and self._relay_service is not None
                        ):
                            _profile = self._conversation_repository._connection.execute(  # noqa: SLF001
                                "SELECT node_id FROM agent_profiles WHERE agent_id = ?",
                                (resolved_target.id,),
                            ).fetchone()
                            if _profile is not None and _profile["node_id"]:
                                _node = str(_profile["node_id"])
                                _relay_result = self._relay_service.enqueue_message_relay(
                                    message=message,
                                    target_node_id=_node,
                                    idempotency_key=f"agent-dm:{message.id}:{resolved_target.id}",
                                    sender_user_id=sender_user_id,
                                    conversation_type="direct",
                                    _override_agent_id=resolved_target.id,
                                )
                                if _relay_result.created:
                                    await self.push_relay_message(
                                        relay_task_id=_relay_result.relay_task.relay_task_id,
                                        target_node_id=_node,
                                        payload=_relay_result.relay_task.payload,
                                    )
                    else:
                        conversation_id = existing["conversation_id"]
                        resolved_target = DispatchTarget(
                            kind=existing["target_kind"],
                            id=existing["target_id"],
                        )
                        message_id = existing["message_id"]
            else:
                conversation_id = existing["conversation_id"]
                resolved_target = DispatchTarget(
                    kind=existing["target_kind"],
                    id=existing["target_id"],
                )
                message_id = existing["message_id"]
        except ValueError as exc:
            return {
                "type": "error",
                "payload": {
                    "code": "invalid_agent_message",
                    "message": str(exc),
                },
            }
        except RuntimeError as exc:
            return {
                "type": "error",
                "payload": {
                    "code": "gateway_not_configured",
                    "message": str(exc),
                },
            }

        if existing is None:
            message_id = message.id
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.message",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "target_kind": resolved_target.kind,
                "target_id": resolved_target.id,
                "source_agent_id": source_agent_id,
            },
        }

    @staticmethod
    def _resolve_source_agent_id_from_dispatch(*, source_raw: str) -> str:
        """Resolve source agent id forwarded in dispatch payload."""
        source_agent_id, _ = GatewayHandler._resolve_dispatch_source_from_session_id(
            source_raw=source_raw
        )
        return source_agent_id

    @staticmethod
    def _resolve_dispatch_source_from_session_id(
        *, source_raw: str
    ) -> tuple[str, str | None]:
        """Resolve source agent id and optional dispatch request id from one source payload."""
        normalized = source_raw.strip()
        if normalized.startswith("agent:"):
            normalized = normalized[len("agent:") :].strip()
        dispatch_request_id = None
        if "|tool_call:" in normalized:
            source_part, dispatch_part = normalized.split("|tool_call:", 1)
            normalized = source_part.strip()
            dispatch_request_id = dispatch_part.strip() or None
            if dispatch_request_id is None:
                raise ValueError("from_session_id tool_call suffix must be non-empty")
        if not normalized:
            raise ValueError("from_session_id must carry source agent id")
        return (normalized, dispatch_request_id)

    async def _handle_system_message(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist one server-originated system notification into an IM conversation.

        System messages are non-first-person notifications injected by the gateway
        (e.g. self_evolution_review notifications).  They use ``sender_type='system'``
        so the IM frontend can render them with a distinct visual style.

        Args:
            payload: Must include ``conversation_id`` (str) and ``text`` (str).

        Returns:
            Ack dict with ``message_id`` on success, or error dict on failure.
        """
        if self._conversation_repository is None or self._message_repository is None:
            return {
                "type": "error",
                "payload": {
                    "code": "gateway_not_configured",
                    "message": "conversation_repository must be configured",
                },
            }

        try:
            conversation_id = _require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            ).strip()
            text = _require_text(payload.get("text"), field_name="text").strip()

            # Resolve or lazily create the well-known system user.
            # The system user has username='system'; its owner_id equals its own id.
            system_user = (
                self._user_repository.get_user_by_username(username="system")
                if self._user_repository is not None
                else None
            )
            if system_user is None and self._user_repository is not None:
                system_user = self._user_repository.create_user(
                    username="system",
                    display_name="System",
                )
            if system_user is None:
                return {
                    "type": "error",
                    "payload": {
                        "code": "system_user_unavailable",
                        "message": "could not resolve system user",
                    },
                }

            message = self._message_repository.create_message(
                conversation_id=conversation_id,
                sender_user_id=system_user.id,
                sender_type="system",
                content=text,
            )
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.system_message",
                    "message_id": message.id,
                },
            }
        except ValueError as exc:
            return {
                "type": "error",
                "payload": {"code": "invalid_system_message", "message": str(exc)},
            }

    def _ensure_agent_message_dispatch_table(self) -> None:
        if self._conversation_repository is None:
            return
        self._conversation_repository._connection.execute(  # noqa: SLF001
            """
            CREATE TABLE IF NOT EXISTS agent_message_dispatch_log (
                dispatch_request_key TEXT PRIMARY KEY,
                source_agent_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conversation_repository._connection.commit()  # noqa: SLF001

    def _find_dispatched_agent_message(
        self, *, dispatch_request_key: str | None
    ) -> dict[str, str] | None:
        if dispatch_request_key is None or self._conversation_repository is None:
            return None
        row = self._conversation_repository._connection.execute(  # noqa: SLF001
            """
            SELECT target_kind, target_id, conversation_id, message_id
            FROM agent_message_dispatch_log
            WHERE dispatch_request_key = ?
            """,
            (dispatch_request_key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "target_kind": str(row["target_kind"]),
            "target_id": str(row["target_id"]),
            "conversation_id": str(row["conversation_id"]),
            "message_id": str(row["message_id"]),
        }

    def _record_dispatched_agent_message(
        self,
        *,
        dispatch_request_key: str,
        source_agent_id: str,
        target_kind: str,
        target_id: str,
        conversation_id: str,
        message_id: str,
    ) -> None:
        if self._conversation_repository is None:
            return
        self._conversation_repository._connection.execute(  # noqa: SLF001
            """
            INSERT INTO agent_message_dispatch_log(
                dispatch_request_key, source_agent_id, target_kind, target_id, conversation_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                dispatch_request_key,
                source_agent_id,
                target_kind,
                target_id,
                conversation_id,
                message_id,
            ),
        )
        self._conversation_repository._connection.commit()  # noqa: SLF001

    def resolve_send_message_target(
        self,
        *,
        source_agent_id: str,
        target: str,
    ) -> tuple[DispatchTarget, str]:
        """Resolve one send_message target into kind + landed conversation_id."""
        if self._conversation_repository is None or self._user_repository is None:
            raise RuntimeError(
                "conversation_repository and user_repository must be configured"
            )
        source_user_id = self._require_user_id_by_username(
            username=f"agent:{source_agent_id}"
        )
        resolved_target = self._classify_dispatch_target(target=target)
        if resolved_target.kind == "conversation_id":
            conversation = self._conversation_repository.get_conversation(
                conversation_id=resolved_target.id
            )
            if conversation is None:
                raise ValueError("conversation_id not found")
            return (resolved_target, conversation.id)
        if resolved_target.kind == "agent_id":
            target_user_id = self._require_user_id_by_username(
                username=f"agent:{resolved_target.id}"
            )
            landed = self._find_or_create_direct_conversation(
                left_user_id=source_user_id,
                right_user_id=target_user_id,
                expected_direct_kind="agent-agent",
            )
            return (resolved_target, landed.id)
        target_user_id = self._require_user_id_by_id(user_id=resolved_target.id)
        landed = self._find_or_create_direct_conversation(
            left_user_id=source_user_id,
            right_user_id=target_user_id,
            expected_direct_kind="user-agent",
        )
        return (resolved_target, landed.id)

    def _classify_dispatch_target(self, *, target: str) -> DispatchTarget:
        """Classify one raw target into conversation_id, agent_id, or user_id."""
        normalized = _require_text(target, field_name="target").strip()
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

        conversation = self._conversation_repository.get_conversation(
            conversation_id=normalized
        )
        if conversation is not None:
            return DispatchTarget(kind="conversation_id", id=normalized)
        by_id = self._user_repository.get_user(user_id=normalized)
        if by_id is not None:
            if by_id.username.startswith("agent:"):
                return DispatchTarget(
                    kind="agent_id",
                    id=by_id.username[len("agent:") :].strip() or by_id.id,
                )
            return DispatchTarget(kind="user_id", id=by_id.id)
        agent_row = self._find_user_by_username(username=f"agent:{normalized}")
        if agent_row is not None:
            return DispatchTarget(kind="agent_id", id=normalized)
        raise ValueError("target not found")

    def _find_or_create_direct_conversation(
        self,
        *,
        left_user_id: str,
        right_user_id: str,
        expected_direct_kind: str,
        caller_owner_id: str | None = None,
    ):  # noqa: ANN202
        """Resolve one canonical direct conversation, creating it when absent.

        Args:
            caller_owner_id: The authenticated caller's owner_id.  When supplied, the
                created conversation's owner_id is set to this value so that
                ``list_conversations_for_owner`` can surface it to the caller.
                For heartbeat delivery the caller is the owner user (to_user_id).
        """
        existing = self._find_canonical_direct_conversation(
            left_user_id=left_user_id,
            right_user_id=right_user_id,
            expected_direct_kind=expected_direct_kind,
        )
        if existing is not None:
            return existing
        return self._conversation_repository.create_conversation(
            title=self._build_default_direct_conversation_title(
                left_user_id=left_user_id,
                right_user_id=right_user_id,
                expected_direct_kind=expected_direct_kind,
            ),
            participant_ids=[left_user_id, right_user_id],
            creator_id=left_user_id,
            caller_owner_id=caller_owner_id,
        )

    def _build_default_direct_conversation_title(
        self,
        *,
        left_user_id: str,
        right_user_id: str,
        expected_direct_kind: str,
    ) -> str:
        if self._conversation_repository is None:
            return "Direct conversation"
        placeholders = ",".join("?" for _ in (left_user_id, right_user_id))
        rows = self._conversation_repository._connection.execute(  # noqa: SLF001
            f"SELECT id, username, display_name FROM users WHERE id IN ({placeholders})",  # noqa: S608
            (left_user_id, right_user_id),
        ).fetchall()
        row_by_id = {str(row["id"]): row for row in rows}
        left_user = row_by_id.get(left_user_id)
        right_user = row_by_id.get(right_user_id)

        def _display_name(row: object | None) -> str | None:
            if row is None:
                return None
            display_name = str(row["display_name"] or "").strip()  # type: ignore[index]
            if display_name:
                return display_name
            username = str(row["username"] or "").strip()  # type: ignore[index]
            if username.startswith("agent:"):
                return username[len("agent:") :].strip() or None
            return username or None

        if expected_direct_kind == "user-agent":
            for row in (left_user, right_user):
                username = str(row["username"] or "").strip() if row is not None else ""
                if username.startswith("agent:"):
                    agent_name = _display_name(row)
                    if agent_name:
                        return agent_name

        return (
            _display_name(right_user)
            or _display_name(left_user)
            or "Direct conversation"
        )

    def _find_canonical_direct_conversation(
        self,
        *,
        left_user_id: str,
        right_user_id: str,
        expected_direct_kind: str,
    ):  # noqa: ANN202
        """Return the canonical direct conversation for one participant pair."""
        pair = {left_user_id, right_user_id}
        direct_candidates = [
            item
            for item in self._conversation_repository.list_conversations()
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

    def _find_user_by_username(self, *, username: str):  # noqa: ANN202
        if self._user_repository is None:
            return None
        return self._conversation_repository._connection.execute(  # noqa: SLF001
            "SELECT id, username, display_name, owner_id FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    def _require_user_id_by_username(self, *, username: str) -> str:
        row = self._find_user_by_username(username=username)
        if row is None:
            raise ValueError(f"username not found: {username}")
        return str(row["id"])

    def _require_user_id_by_id(self, *, user_id: str) -> str:
        user = self._user_repository.get_user(user_id=user_id)
        if user is None:
            raise ValueError("user_id not found")
        return str(user.id)

    def record_relay_failure(
        self,
        *,
        conversation_id: str,
        message_id: str,
        relay_task_id: str,
        target_node_id: str,
        reason: str,
        guidance: str,
    ) -> None:
        """Persist actionable conversation events for relay failures before execution starts."""
        if self._event_repository is None:
            return
        base_payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "relay_task_id": relay_task_id,
            "target_node_id": target_node_id,
            "reason": reason,
            "guidance": guidance,
            "progress_state": "failed",
            "semantic": "relay_failed_before_processing",
        }
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="relay.failed",
            delivery_status="failed",
            payload=base_payload,
        )
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="conversation.notice",
            delivery_status="failed",
            payload={
                **base_payload,
                "notice_type": "action_required",
            },
        )
        self._event_repository.update_message_delivery_status(
            message_id=message_id,
            delivery_status="failed",
        )

    def _persist_receipt_events(
        self, *, task, node_id: str, detail: str | None
    ) -> None:  # noqa: ANN001
        if self._event_repository is None:
            return
        progress_map = {
            "sent": ("relay.accepted", "accepted", "accepted_by_gateway"),
            "completed": ("relay.completed", "completed", "agent_run_completed"),
            "failed": ("relay.failed", "failed", "agent_run_failed"),
        }
        event_type, progress_state, semantic = progress_map[
            task.receipt_status or task.status
        ]
        payload = {
            "conversation_id": task.conversation_id,
            "message_id": task.message_id,
            "relay_task_id": task.relay_task_id,
            "target_node_id": task.target_node_id,
            "node_id": node_id,
            "agent_id": task.payload.get("agent_id"),
            "idempotency_key": task.idempotency_key,
            "relay_metadata": task.payload.get("metadata", {}),
            "detail": detail,
            "progress_state": progress_state,
            "semantic": semantic,
        }
        self._event_repository.append_event(
            conversation_id=task.conversation_id,
            message_id=task.message_id,
            event_type=event_type,
            delivery_status=task.status,
            payload=payload,
        )
        if progress_state == "completed":
            self._event_repository.append_event(
                conversation_id=task.conversation_id,
                message_id=task.message_id,
                event_type="message.delivered",
                delivery_status="completed",
                payload={
                    **payload,
                    "progress_state": "completed",
                    "semantic": "agent_run_completed",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=task.message_id,
                delivery_status="completed",
            )
        elif progress_state == "failed":
            self._event_repository.append_event(
                conversation_id=task.conversation_id,
                message_id=task.message_id,
                event_type="conversation.notice",
                delivery_status="failed",
                payload={
                    **payload,
                    "notice_type": "action_required",
                    "guidance": "检查目标节点连接、查看执行日志后重试；如持续失败可切换节点。",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=task.message_id,
                delivery_status="failed",
            )

    def _persist_report_event(self, *, payload: dict[str, object]) -> None:
        if self._event_repository is None:
            return
        conversation_id = _require_text(
            payload.get("conversation_id"), field_name="conversation_id"
        )
        message_id = _require_text(payload.get("message_id"), field_name="message_id")
        status = _require_text(payload.get("status"), field_name="status")
        summary = _optional_text(payload.get("summary"))
        run_id = _optional_text(payload.get("run_id"))
        guidance = _optional_text(payload.get("guidance"))
        progress_state = (
            "processing"
            if status == "running"
            else ("completed" if status == "completed" else "failed")
        )
        semantic = (
            "agent_run_processing"
            if progress_state == "processing"
            else (
                "agent_run_completed"
                if progress_state == "completed"
                else "agent_run_failed"
            )
        )
        report_payload: dict[str, object] = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "node_id": _require_text(payload.get("node_id"), field_name="node_id"),
            "run_id": run_id,
            "summary": summary,
            "status": status,
            "progress_state": progress_state,
            "semantic": semantic,
            "guidance": guidance,
        }
        # Carry token_usage in relay.report so the browser Token Chip can render real counts.
        usage = _optional_usage(payload.get("usage"))
        if usage is not None and progress_state == "completed":
            report_payload["token_usage"] = {
                "prompt": usage["prompt_tokens"],
                "completion": usage["completion_tokens"],
                "total": usage["total_tokens"],
            }
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="relay.processing"
            if progress_state == "processing"
            else "relay.report",
            delivery_status=status,
            payload=report_payload,
        )
        if progress_state == "failed":
            self._event_repository.append_event(
                conversation_id=conversation_id,
                message_id=message_id,
                event_type="conversation.notice",
                delivery_status="failed",
                payload={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "run_id": run_id,
                    "summary": summary,
                    "status": status,
                    "progress_state": "failed",
                    "semantic": "agent_run_failed",
                    "guidance": guidance
                    or "检查节点连接和执行日志后重试；如需要可重新发送消息。",
                    "notice_type": "action_required",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=message_id,
                delivery_status="failed",
            )

    def _persist_report_usage(self, *, payload: dict[str, object]) -> None:
        if self._metrics_service is None or self._conversation_repository is None:
            return
        if _optional_text(payload.get("status")) != "completed":
            return
        conversation_id = _optional_text(payload.get("conversation_id"))
        usage = _optional_usage(payload.get("usage"))
        if conversation_id is None or usage is None:
            return
        conversation = self._conversation_repository.get_conversation(
            conversation_id=conversation_id
        )
        owner_id = conversation.owner_id if conversation is not None else None
        self._metrics_service.record_usage(
            owner_id=owner_id,
            conversation_id=None,
            agent_id=None,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            turns=1,
        )
        self._metrics_service.record_usage(
            owner_id=owner_id,
            conversation_id=conversation_id,
            agent_id=None,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            turns=1,
        )
        agent_id = _optional_text(payload.get("agent_id"))
        if agent_id is not None:
            self._metrics_service.record_usage(
                owner_id=owner_id,
                conversation_id=conversation_id,
                agent_id=agent_id,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                turns=1,
            )


def _encode_status_frame(*, event_type: str, payload: dict[str, object]) -> str:
    """Encode one status-change frame for the browser user stream.

    Mirrors ``encode_user_stream_event_frame`` shape (op=event, event_type, data)
    so the SPA reducer can dispatch by ``event_type`` without a separate parser.
    """
    body = {"op": "event", "event_type": event_type, "data": payload}
    return json.dumps(body, ensure_ascii=True, separators=(",", ":"))


def _decode_message(raw_message: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("message must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("message must be a JSON object")
    return parsed


def _require_message_type(payload: dict[str, Any]) -> str:
    return _require_text(payload.get("type"), field_name="type")


# WS-layer strict field helpers — intentionally NOT unified with IM/infra/_helpers.py.
# At the WS boundary a missing or non-string required field means the gateway sent a
# malformed frame, which is a protocol error.  Fail-fast here (raise ValueError/
# RuntimeError) prevents silently routing bad data into the domain layer.
# The _helpers.py variants return None on missing values; that lenient behaviour is
# correct for HTTP request parsing, not for WS frames where the schema is contract-level.
def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_dict(value: object, *, field_name: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_string_list(value: object, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return [item for item in value]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings when provided")
    stripped = value.strip()
    return stripped or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("optional integer fields must be integers when provided")
    return value


def _optional_dict(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("optional object fields must be objects when provided")
    return value


def _optional_usage(value: object) -> dict[str, int] | None:
    if value is None:
        return None
    payload = _require_dict(value, field_name="usage")
    prompt_tokens = _optional_int(payload.get("prompt_tokens"))
    completion_tokens = _optional_int(payload.get("completion_tokens"))
    if prompt_tokens is None or completion_tokens is None:
        return None
    total_tokens = _optional_int(payload.get("total_tokens"))
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": max(prompt_tokens, 0),
        "completion_tokens": max(completion_tokens, 0),
        "total_tokens": max(total_tokens, 0),
    }


def _parse_token_usage(value: object) -> TokenUsage | None:
    """Parse a streaming_delta token_usage dict into a TokenUsage domain object."""
    if value is None or not isinstance(value, dict):
        return None
    prompt = value.get("prompt") or value.get("prompt_tokens")
    completion = value.get("completion") or value.get("completion_tokens")
    total = value.get("total") or value.get("total_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    if not isinstance(total, int):
        total = prompt + completion
    # context_window is the model's actual maximum context size, passed through from
    # the kernel's CompactionSettings.context_window via the turn_end event chain.
    # 0 means unknown (kernel didn't send it); the frontend treats 0 as "not available".
    cw_raw = value.get("context_window")
    context_window = max(int(cw_raw), 0) if isinstance(cw_raw, int) else 0
    return TokenUsage(
        output=max(completion, 0),
        context_used=max(prompt, 0),
        context_window=context_window,
        total=max(total, 0),
    )


def _parse_tool_call(value: object) -> ToolCall:
    """Parse a streaming_delta tool_call dict into a ToolCall domain object."""
    if not isinstance(value, dict):
        raise ValueError("tool_call must be an object")
    tc_id = str(value.get("id") or "")
    name = str(value.get("name") or "")
    status = str(value.get("status") or "running")
    input_data = value.get("input") or {}
    if not isinstance(input_data, dict):
        input_data = {}
    duration_ms = value.get("duration_ms")
    output = value.get("output")
    return ToolCall(
        id=tc_id,
        name=name,
        status=status,  # type: ignore[arg-type]
        input=input_data,
        duration_ms=int(duration_ms) if isinstance(duration_ms, (int, float)) else None,
        output=str(output) if output is not None else None,
    )


def _not_registered_error(*, node_id: str) -> dict[str, object]:
    return {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": f"node {node_id} is not registered",
        },
    }
