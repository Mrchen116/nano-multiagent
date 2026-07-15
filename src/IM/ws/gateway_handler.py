"""Gateway WebSocket connection manager (see docs/specs/im/spec.md)."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import contextlib
import json
import logging
from typing import Any
from uuid import uuid4

_logger = logging.getLogger(__name__)

from fastapi import WebSocket, WebSocketDisconnect

from IM.api.ws.event_types import (
    EVENT_AGENT_CHANNEL_STATUS_CHANGED,
    EVENT_AGENT_STATUS_CHANGED,
    EVENT_NODE_STATUS_CHANGED,
    build_agent_channel_status_changed_payload,
    build_agent_status_changed_payload,
    build_node_status_changed_payload,
)
from IM.application.event_bridge import EventBridge
from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.domain.models import (
    Actor,
    Message,
    NodeStatus,
    TokenUsage,
    ToolCall,
)
from IM.infra.gateway_persistence import (
    AgentDispatchRecord,
    DispatchTarget,
    GatewayConversationPersistence,
    GatewayNodePersistence,
)
from IM.infra.channel_control_store import ChannelControlStore, ChannelManifest
from IM.infra.repositories import (
    EventRepository,
    MessageRepository,
)
from IM.ws.user_stream import UserStreamRegistry
from IM.ws.gateway_protocol import (
    parse_delivery_receipt_event,
    parse_node_report_event,
    parse_streaming_delta_event,
)


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
        node_persistence: GatewayNodePersistence | None = None,
        conversation_persistence: GatewayConversationPersistence | None = None,
        message_repository: MessageRepository | None = None,
        event_repository: EventRepository | None = None,
        metrics_service: MetricsService | None = None,
        user_stream_registry: UserStreamRegistry | None = None,
        event_bridge: EventBridge | None = None,
        channel_control_store: ChannelControlStore | None = None,
    ) -> None:
        self._relay_service = relay_service
        self._node_persistence = node_persistence
        self._conversation_persistence = conversation_persistence
        self._message_repository = message_repository
        self._event_repository = event_repository
        self._metrics_service = metrics_service
        self._user_stream_registry = user_stream_registry
        self._channel_control_store = channel_control_store
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
        self._channel_initialization_locks: dict[str, asyncio.Lock] = {}
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
        # feat-394-M13 (决策 G): gateway-side state via WS RPC — IM never directly reads
        # gateway workspace files because IM and gateway may run on different hosts.
        self._heartbeat_md_waiters: dict[str, asyncio.Future[str | None]] = {}
        self._cron_jobs_waiters: dict[str, asyncio.Future[list | None]] = {}
        self._cron_delete_waiters: dict[str, asyncio.Future[bool | None]] = {}
        self._skills_usage_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}
        # feat-445-M1: session.fork.request → session.fork.result futures.
        self._session_fork_waiters: dict[
            str, asyncio.Future[dict[str, object] | None]
        ] = {}

    async def serve(
        self, websocket: WebSocket, *, authenticated_owner_id: str = ""
    ) -> None:
        """Accept one websocket and process gateway protocol frames until disconnect.

        Args:
            websocket: Authenticated Gateway transport owned by the caller.
            authenticated_owner_id: Owner scope derived from the bearer token by
                the HTTP/WebSocket composition boundary.
        """
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
                    authenticated_owner_id=authenticated_owner_id,
                )
                if response is not None:
                    await websocket.send_json(response)
                if message_type == "node.register":
                    node_id = str(body["node_id"])
                    await self.initialize_channel_control(node_id=node_id)
        except WebSocketDisconnect:
            pass
        finally:
            if node_id is not None:
                await self.disconnect(
                    node_id=node_id,
                    expected_websocket=websocket,
                )

    async def handle_message(
        self,
        *,
        websocket: WebSocket,
        message_type: str,
        payload: dict[str, object],
        authenticated_owner_id: str = "",
    ) -> dict[str, object] | None:
        """Handle one gateway->IM protocol message and return optional ack/error."""
        if message_type == "node.register":
            return await self._handle_register(
                websocket=websocket,
                payload=payload,
                authenticated_owner_id=authenticated_owner_id,
            )
        if authenticated_owner_id:
            await self._authorize_upstream_frame(
                websocket=websocket,
                payload=payload,
                authenticated_owner_id=authenticated_owner_id,
            )
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
        if message_type == "node.heartbeat.md":
            return await self._handle_heartbeat_md(payload=payload)
        if message_type == "node.cron.jobs":
            return await self._handle_cron_jobs(payload=payload)
        if message_type == "node.cron.delete":
            return await self._handle_cron_delete(payload=payload)
        if message_type == "node.skills.usage":
            return await self._handle_skills_usage(payload=payload)
        if message_type == "session.fork.result":
            return await self._handle_session_fork_result(payload=payload)
        if message_type == "channel.reconcile.result":
            return await self._handle_channel_reconcile_result(
                websocket=websocket, payload=payload
            )
        if message_type == "channels.bootstrap":
            return await self._handle_channel_bootstrap(
                websocket=websocket, payload=payload
            )
        if message_type == "channel.status":
            return await self._handle_channel_status(websocket=websocket, payload=payload)
        if message_type == "channel.runtime_metadata":
            return await self._handle_channel_runtime_metadata(
                websocket=websocket, payload=payload
            )
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
            await self.disconnect(
                node_id=target_node_id,
                expected_websocket=connection.websocket,
            )
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

    async def push_channel_reconcile(self, manifest: ChannelManifest) -> bool:
        """Push one authoritative full desired snapshot to its connected node."""
        return await self._push_downstream(
            target_node_id=manifest.node_id,
            message_type="channel.reconcile",
            payload=manifest.as_payload(request_id=uuid4().hex),
        )

    async def push_channel_reconnect(
        self, *, target_node_id: str, channel_id: str, channel_revision: int
    ) -> bool:
        """Push one ephemeral reconnect action without changing desired state."""
        return await self._push_downstream(
            target_node_id=target_node_id,
            message_type="channel.reconnect",
            payload={
                "channel_id": channel_id,
                "channel_revision": channel_revision,
            },
        )

    async def initialize_channel_control(self, *, node_id: str) -> bool:
        """Initialize once after register/bind or replay current desired state."""
        store = self._channel_control_store
        if store is None:
            return False
        lock = self._channel_initialization_locks.setdefault(
            node_id, asyncio.Lock()
        )
        async with lock:
            connection = await self.snapshot_connection(node_id=node_id)
            if (
                connection is None
                or not connection.credential_key_id
                or not connection.credential_algorithm
                or not connection.credential_public_key
            ):
                return False
            durable_owner = store.current_owner_for_node(node_id=node_id)
            if durable_owner and durable_owner != connection.owner_id:
                store.remove_node_public_key(node_id=node_id)
                await self.disconnect(
                    node_id=node_id, expected_websocket=connection.websocket
                )
                with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                    await connection.websocket.close(code=1008)
                return False
            registered = store.register_bound_node_public_key(
                node_id=node_id,
                key_id=connection.credential_key_id,
                algorithm=connection.credential_algorithm,
                public_key=connection.credential_public_key,
            )
            if not registered:
                return False
            if connection.capabilities.get("channel_bootstrap") is not True:
                return True
            state, manifest = store.prepare_initialization(node_id=node_id)
            if state == "bootstrap_required":
                return await self._push_downstream(
                    target_node_id=node_id,
                    message_type="channels.bootstrap.request",
                    payload={
                        "request_id": uuid4().hex,
                        "node_id": node_id,
                        "owner_id": store.current_owner_for_node(node_id=node_id),
                    },
                )
            if manifest is not None:
                return await self.push_channel_reconcile(manifest)
            return state == "waiting_for_owner"

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
        reason: str | None = None,
    ) -> bool:
        """Push a permission_response frame to the gateway node hosting the parked run.

        The PA side consumes this frame and forwards the decision to the agent inbound
        endpoint so the parked hook can resume.

        Args:
            target_node_id: Node that owns the agent run awaiting the decision.
            message_id: Agent message that embeds the permission request.
            request_id: Stable permission request identifier.
            decision: User-chosen option (e.g. ``"allow_once"``, ``"deny"``).
            reason: feat-440-M1 — optional free-text deny reason. Normalized to ""
                here (single normalization point) so old callers / allow decisions
                produce a stable frame and PermissionResponse.reason ends up empty.

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
                "reason": reason or "",
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

    async def request_fork_session(
        self,
        *,
        target_node_id: str,
        source_conversation_id: str,
        new_conversation_id: str,
        agent_id: str,
        fork_message_id: str,
        source_external_source: str | None = None,
        source_external_chat_id: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object] | None:
        """Delegate a session fork to one gateway node and await its result.

        feat-445-M1 (decision 2): the gateway holds the conversation↔session binding, so
        IM can only fork by asking it. Returns the result dict ({ok, new_session_id?,
        error?}) or ``None`` when the node is not connected / times out (the caller then
        rolls back the half-built conversation).
        """
        request_id = f"session-fork-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._session_fork_waiters[request_id] = waiter
        payload: dict[str, object] = {
            "request_id": request_id,
            "source_conversation_id": source_conversation_id,
            "new_conversation_id": new_conversation_id,
            "agent_id": agent_id,
            "fork_point": {"message_id": fork_message_id},
        }
        if source_external_source:
            payload["source_external_source"] = source_external_source
        if source_external_chat_id:
            payload["source_external_chat_id"] = source_external_chat_id
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="session.fork.request",
                payload=payload,
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._session_fork_waiters.pop(request_id, None)

    async def _handle_session_fork_result(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        # Echo through the gateway's reported result (ok / new_session_id / error).
        result = {k: v for k, v in payload.items() if k not in {"node_id"}}
        async with self._lock:
            waiter = self._session_fork_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(result)
        return {
            "type": "ack",
            "payload": {
                "message_type": "session.fork.result",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

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

    async def request_node_heartbeat_md(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> str | None:
        """Send a node.heartbeat.md.request frame and await the HEARTBEAT.md content.

        feat-394-M13 (决策 G): IM must never directly read gateway workspace files.
        This RPC asks the target gateway node to read <workspace>/HEARTBEAT.md and
        return its raw content.  The IM host and gateway may run on different machines,
        so direct file access from IM is not viable.

        Returns:
            Raw HEARTBEAT.md text, empty string when the file does not exist, or None
            when the node is not connected / times out (graceful degradation).
        """
        request_id = f"heartbeat-md-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[str | None] = loop.create_future()
        async with self._lock:
            self._heartbeat_md_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="node.heartbeat.md.request",
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
                self._heartbeat_md_waiters.pop(request_id, None)

    async def request_node_cron_jobs(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> list | None:
        """Send a node.cron.jobs.request frame and await the job list.

        feat-394-M13 (决策 G): replaces direct IM-side read of
        <workspace>/.nanoassistant/cron/jobs.json.  The gateway reads its own file
        and returns the job list; IM never touches the workspace directory.

        Returns:
            List of job dicts, empty list when no jobs file exists yet, or None when
            the node is not connected / times out (graceful degradation).
        """
        request_id = f"cron-jobs-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[list | None] = loop.create_future()
        async with self._lock:
            self._cron_jobs_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="node.cron.jobs.request",
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
                self._cron_jobs_waiters.pop(request_id, None)

    async def request_node_cron_delete(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        job_id: str,
        timeout_seconds: float = 10.0,
    ) -> bool | None:
        """Send a node.cron.delete.request frame and await the deletion result.

        feat-394-M13 (决策 G): replaces direct IM-side write of
        <workspace>/.nanoassistant/cron/jobs.json.  The gateway performs the delete
        on its own filesystem and reports whether the job was found and removed.

        Returns:
            True when the job was found and deleted, False when job_id was not found,
            or None when the node is not connected / times out (graceful degradation).
        """
        request_id = f"cron-delete-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[bool | None] = loop.create_future()
        async with self._lock:
            self._cron_delete_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="node.cron.delete.request",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                    "job_id": job_id,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._cron_delete_waiters.pop(request_id, None)

    async def request_node_skills_usage(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object] | None:
        """Send a node.skills.usage.request frame and await usage stats.

        feat-446-M4: the authoritative ``.usage.json`` file is stored in the
        gateway-side workspace.  IM delegates the read/aggregation over WS RPC
        so IM and gateway can run on different hosts.
        """
        request_id = f"skills-usage-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._skills_usage_waiters[request_id] = waiter
        try:
            pushed = await self._push_downstream(
                target_node_id=target_node_id,
                message_type="node.skills.usage.request",
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
                self._skills_usage_waiters.pop(request_id, None)

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

    async def _broadcast_channel_status_change(
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

    async def _handle_register(
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

    async def _authorize_upstream_frame(
        self,
        *,
        websocket: WebSocket,
        payload: dict[str, object],
        authenticated_owner_id: str,
    ) -> GatewayConnection:
        """Bind every upstream business frame to its authenticated live socket.

        The websocket registration is the routing authority. Payload ``node_id`` is
        only an assertion and may never select a different connection. Older Gateway
        clients that omitted it are normalized after the same checks, keeping the
        mutation handlers on one trusted node identity.
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

    async def _handle_heartbeat(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
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

    async def _handle_channel_reconcile_result(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist an applied head and acknowledge the Gateway upstream FIFO item."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._is_registered_sender(websocket=websocket, node_id=node_id):
            return _not_registered_error(node_id=node_id)
        manifest_revision = _optional_int(payload.get("manifest_revision"))
        if manifest_revision is None:
            raise ValueError("manifest_revision is required")
        legacy_outcomes = payload.get("outcomes")
        modern = "outcome" in payload
        outcome = str(payload.get("outcome") or "")
        applied_channel_ids = payload.get("applied_channel_ids")
        failures = payload.get("failures")
        if not modern:
            normalized = legacy_outcomes if isinstance(legacy_outcomes, list) else []
            applied_channel_ids = [
                item.get("channel_id")
                for item in normalized
                if isinstance(item, dict) and item.get("outcome") == "applied"
            ]
            failures = [
                item
                for item in normalized
                if isinstance(item, dict) and item.get("outcome") != "applied"
            ]
            outcome = "retryable_failed" if failures else "applied"
        acknowledgement: dict[str, object] = {
            "head_outcome": "accepted",
            "removal_token_outcomes": [],
        }
        if self._channel_control_store is not None:
            acknowledgement = self._channel_control_store.record_reconcile_result(
                node_id=node_id,
                manifest_revision=manifest_revision,
                outcome=outcome,
                applied_channel_ids=applied_channel_ids,
                removal_outcomes=payload.get("removal_outcomes"),
                failures=failures,
            )
        if modern:
            return {
                "type": "channels.reconcile.result.ack",
                "payload": {
                    "request_id": request_id,
                    "manifest_revision": manifest_revision,
                    **acknowledgement,
                },
            }
        return {
            "type": "ack",
            "payload": {
                "message_type": "channel.reconcile.result",
                "request_id": request_id,
            },
        }

    async def _handle_channel_bootstrap(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Commit a legacy snapshot once and return its authoritative manifest."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._is_registered_sender(websocket=websocket, node_id=node_id):
            return _not_registered_error(node_id=node_id)
        store = self._channel_control_store
        if store is None:
            return {
                "type": "error",
                "payload": {
                    "code": "channel_control_unavailable",
                    "request_id": request_id,
                },
            }
        outcome, manifest = store.bootstrap_channels(
            node_id=node_id, items=payload.get("items")
        )
        return {
            "type": "channels.bootstrap.result",
            "payload": {
                "request_id": request_id,
                "outcome": outcome,
                "manifest": manifest.as_payload(request_id=uuid4().hex),
            },
        }

    async def _handle_channel_status(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Return a normal correlated result for every semantic status outcome."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._is_registered_sender(websocket=websocket, node_id=node_id):
            return _not_registered_error(node_id=node_id)
        result = (
            self._channel_control_store.record_status_result(payload)
            if self._channel_control_store is not None
            else None
        )
        outcome = result.outcome if result is not None else "terminal_channel_removed"
        if (
            outcome == "accepted"
            and result is not None
            and result.owner_id is not None
            and result.agent_id is not None
            and result.channel_id is not None
        ):
            await self._broadcast_channel_status_change(
                owner_id=result.owner_id,
                agent_id=result.agent_id,
                channel_id=result.channel_id,
            )
        return {
            "type": "channel.status.result",
            "payload": {"request_id": request_id, "outcome": outcome},
        }

    async def _handle_channel_runtime_metadata(
        self, *, websocket: WebSocket, payload: dict[str, object]
    ) -> dict[str, object]:
        """Apply generation-scoped provider identity metadata and correlate result."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        if not await self._is_registered_sender(websocket=websocket, node_id=node_id):
            return _not_registered_error(node_id=node_id)
        outcome = (
            self._channel_control_store.record_provider_metadata(payload)
            if self._channel_control_store is not None
            else "terminal_channel_removed"
        )
        return {
            "type": "channel.runtime_metadata.result",
            "payload": {"request_id": request_id, "outcome": outcome},
        }

    async def _is_registered_sender(
        self, *, websocket: WebSocket, node_id: str
    ) -> bool:
        async with self._lock:
            connection = self._connections.get(node_id)
            return connection is not None and connection.websocket is websocket

    async def _handle_report(self, *, payload: dict[str, object]) -> dict[str, object]:
        # Validate node_id first; a missing or empty node_id means the payload is structurally
        # invalid and we cannot even look up the connection. Return an error frame so the Gateway
        # knows the frame was rejected, but keep the WS connection alive.
        try:
            event = parse_node_report_event(payload)
            node_id = event.node_id
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
        - ``message_discarded``: silent run; EventBridge removes the provisional message.
        - ``tool_call_upserted``: tool call started; EventBridge upserts tool_calls JSON.
        - ``tool_call_completed``: tool call done; EventBridge settles tool_calls JSON.

        Cross-tenant isolation: every frame carries ``owner_id``; EventBridge → notify callback
        → build_notify_enqueue reads conversation_participants which already gates by owner.
        The broadcast_to_users path is never called here (streaming delta is owner-scoped only).
        """
        if self._event_bridge is None:
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta"}}

        event = parse_streaming_delta_event(payload)
        kind = event.kind

        if kind == "turn_start":
            agent_id = _require_text(event.agent_id, field_name="agent_id")
            to_user_id = event.to_user_id
            raw_conversation_id = event.conversation_id

            if to_user_id is not None and raw_conversation_id is None:
                # feat-393: heartbeat/cron lazy-resolution mode.  Gateway sends to_user_id
                # (the owner) instead of conversation_id; we resolve/create the canonical
                # (owner, agent) direct conversation here, then fall through to the shared
                # on_turn_start path.  The ack returns both conversation_id and message_id
                # so the gateway can seed run_context_store with both values.
                #
                # Two modes are mutually exclusive: conversation_id → normal eager-bubble
                # path (unchanged); to_user_id → lazy canonical-conv resolution path.
                if self._conversation_persistence is None:
                    return {
                        "type": "ack",
                        "payload": {
                            "message_type": "node.streaming_delta",
                            "kind": kind,
                            "skipped": "repositories_not_configured",
                        },
                    }
                agent_user_id = event.agent_user_id
                if agent_user_id is None:
                    agent_user_id = self._conversation_persistence.agent_user_id(
                        agent_id=agent_id
                    )
                    if agent_user_id is None:
                        return {
                            "type": "ack",
                            "payload": {
                                "message_type": "node.streaming_delta",
                                "kind": kind,
                                "skipped": "agent_user_id_not_found",
                            },
                        }
                # feat-393 fix-r1: owner lookup / canonical-conv creation can fail when
                # config.node.user_id is stale or the ephemeral IM DB has no such user yet.
                # Must NOT raise out of this handler — that would close the WS connection and
                # cause the Gateway to reconnect immediately, producing the 413-open/close flap
                # seen in round-1 acceptance (refactor-387 "坏帧关连接" pattern re-introduced).
                # Per design decision-6: delivery failure ≠ run failure; log and return skipped
                # ack so the Gateway can continue and this heartbeat run completes normally.
                try:
                    conversation_id = self._conversation_persistence.resolve_user_agent_conversation(
                        agent_id=agent_id,
                        user_id=to_user_id,
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
                    conversation_id=conversation_id,
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
                        "conversation_id": conversation_id,
                        "message_id": created_message.id,
                    },
                }

            # Normal path: conversation_id is provided (eager placeholder for regular chat).
            conversation_id = _require_text(
                payload.get("conversation_id"), field_name="conversation_id"
            )
            # Resolve IM user ID from agent_id; gateway sends agent_id (e.g. "alpha"),
            # IM stores the agent as username="agent:<agent_id>" in the users table.
            agent_user_id = event.agent_user_id
            if agent_user_id is None and self._conversation_persistence is not None:
                agent_user_id = self._conversation_persistence.agent_user_id(
                    agent_id=agent_id
                )
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
            message_id = _require_text(event.message_id, field_name="message_id")
            delta_text = event.delta_text or ""
            self._event_bridge.on_message_delta(
                message_id=message_id, delta_text=delta_text
            )

        elif kind == "message_completed":
            message_id = _require_text(event.message_id, field_name="message_id")
            final_content = event.final_content
            token_usage = _parse_token_usage(event.token_usage)
            raw_ds = event.delivery_status
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
            # feat-445-M1: per-bubble kernel message_id forwarded by the gateway relay so
            # this bubble row is stamped with the assistant message that produced it.
            kernel_message_id = event.kernel_message_id
            self._event_bridge.on_message_completed(
                message_id=message_id,
                final_content=final_content,
                token_usage=token_usage,
                delivery_status=ds,
                kernel_message_id=kernel_message_id,
            )

        elif kind == "message_discarded":
            message_id = _require_text(event.message_id, field_name="message_id")
            reason = _require_text(event.reason, field_name="reason")
            self._event_bridge.on_message_discarded(
                message_id=message_id, reason=reason
            )

        elif kind == "run_heartbeat":
            # bugfix-417-M3 R4: kernel liveness heartbeat (tool / LLM-await /
            # parked-permission). EventBridge appends a conversation_events row so the
            # message's last_evt advances and the relay watchdog sees the run as alive —
            # the single uniform liveness signal that replaces the permission marker.
            message_id = _require_text(event.message_id, field_name="message_id")
            source = event.source or ""
            self._event_bridge.on_run_heartbeat(message_id=message_id, source=source)

        elif kind == "thinking_segment":
            # feat-439-M2: 一段思考过程项。EventBridge 持久化进 thinking_json 并广播
            # thinking.segment。seq 在 repo 持久化边界赋予(= 当前 tool_calls 数)。
            message_id = _require_text(event.message_id, field_name="message_id")
            text = event.text or ""
            self._event_bridge.on_thinking_segment(message_id=message_id, text=text)

        elif kind == "tool_call_upserted":
            message_id = _require_text(event.message_id, field_name="message_id")
            tc = _parse_tool_call(event.tool_call)
            self._event_bridge.on_tool_call_upserted(
                message_id=message_id, tool_call=tc
            )

        elif kind == "tool_call_completed":
            message_id = _require_text(event.message_id, field_name="message_id")
            tc = _parse_tool_call(event.tool_call)
            self._event_bridge.on_tool_call_completed(
                message_id=message_id, tool_call=tc
            )

        elif kind == "permission_request":
            # PA → IM: agent is awaiting a user decision; EventBridge persists the pending
            # request and fans out permission.request to connected browser clients.
            message_id = _require_text(event.message_id, field_name="message_id")
            permission_request = event.permission_request
            if not isinstance(permission_request, dict):
                raise ValueError("permission_request must be a dict")
            self._event_bridge.on_permission_request(
                message_id=message_id,
                permission_request=permission_request,
            )

        elif kind == "permission_resolved":
            # PA → IM: user's decision has been forwarded to the agent; update persisted
            # status and notify browser clients so the card can settle.
            message_id = _require_text(event.message_id, field_name="message_id")
            request_id = _require_text(event.request_id, field_name="request_id")
            decision = _require_text(event.decision, field_name="decision")
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
        event = parse_delivery_receipt_event(payload)
        node_id = event.node_id
        relay_task_id = event.relay_task_id
        delivery_status = event.delivery_status
        detail = event.detail
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
        if self._conversation_persistence is None:
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
        route = self._conversation_persistence.group_reply_route(
            conversation_id=task.conversation_id,
            source_agent_id=source_agent_id,
        )
        if route is None:
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
            sender_user_id=route.sender_user_id,
            sender_type="agent",
            sender=Actor(
                type="agent",
                id=source_agent_id,
                display_name=route.sender_display_name,
                user_id=route.sender_user_id,
            ),
            content=detail.strip(),
            attachments=[],
            delivery_status="completed",
            created_at=task.updated_at,
        )
        for target in route.targets:
            target_node_id = self._conversation_persistence.agent_node_id(
                agent_id=target.agent_id
            )
            if target_node_id is None:
                continue
            result = self._relay_service.enqueue_message_relay(
                message=synthetic_message,
                target_node_id=target_node_id,
                idempotency_key=f"agent-reply:{task.relay_task_id}:{target.agent_id}",
                sender_user_id=route.sender_user_id,
                conversation_type="group",
                extra_metadata={
                    "source_agent_id": source_agent_id,
                    "sender_display_name": route.sender_display_name,
                },
                _override_agent_id=target.agent_id,
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
            await self.disconnect(
                node_id=target_node_id,
                expected_websocket=connection.websocket,
            )
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

    async def _handle_heartbeat_md(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve heartbeat-md waiter when gateway returns HEARTBEAT.md content.

        feat-394-M13 (决策 G): gateway sends ``node.heartbeat.md`` in response to
        ``node.heartbeat.md.request`` with {request_id, content}.
        Empty string signals file does not exist; both are valid.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        content_raw = payload.get("content")
        content = content_raw if isinstance(content_raw, str) else ""
        async with self._lock:
            waiter = self._heartbeat_md_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(content)
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.heartbeat.md",
                "request_id": request_id,
            },
        }

    async def _handle_cron_jobs(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve cron-jobs waiter when gateway returns the job list.

        feat-394-M13 (决策 G): gateway sends ``node.cron.jobs`` in response to
        ``node.cron.jobs.request`` with {request_id, jobs:[...]}.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        jobs_raw = payload.get("jobs")
        jobs: list = jobs_raw if isinstance(jobs_raw, list) else []
        async with self._lock:
            waiter = self._cron_jobs_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(jobs)
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.cron.jobs",
                "request_id": request_id,
            },
        }

    async def _handle_cron_delete(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve cron-delete waiter when gateway reports deletion result.

        feat-394-M13 (决策 G): gateway sends ``node.cron.delete`` in response to
        ``node.cron.delete.request`` with {request_id, deleted: bool}.
        deleted=True means job was found and removed; False means not found.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        deleted_raw = payload.get("deleted")
        deleted: bool = bool(deleted_raw)
        async with self._lock:
            waiter = self._cron_delete_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(deleted)
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.cron.delete",
                "request_id": request_id,
            },
        }

    async def _handle_skills_usage(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve skills-usage waiter when gateway returns the dashboard payload."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        usage_raw = payload.get("usage")
        usage: dict[str, object] = usage_raw if isinstance(usage_raw, dict) else {}
        async with self._lock:
            waiter = self._skills_usage_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(usage))
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.skills.usage",
                "request_id": request_id,
            },
        }

    async def _handle_agent_message(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Persist one gateway-dispatched send_message payload into IM conversations.

        For user-target messages (background agent notifications), this method uses
        EventBridge (on_turn_start + on_message_completed) rather than calling
        create_message directly.  That ensures a message.created event is written to
        conversation_events so the front-end user-stream picks it up in real time and
        renders the bubble without a manual refresh.

        For agent-target messages (agent-to-agent relay), the prior direct
        create_message path is preserved — those messages are forwarded via relay and
        the target agent does not need a live WS bubble.
        """
        if self._conversation_persistence is None or self._message_repository is None:
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
            resolution = self._conversation_persistence.resolve_send_target(
                source_agent_id=source_agent_id,
                target=target,
                caller_owner_id=None,
            )
            resolved_target = resolution.target
            conversation_id = resolution.conversation_id
            dispatch_request_key = (
                f"{source_agent_id}:{dispatch_request_id}"
                if dispatch_request_id is not None
                else None
            )
            existing = (
                self._conversation_persistence.find_dispatch(
                    dispatch_request_key=dispatch_request_key
                )
                if dispatch_request_key is not None
                else None
            )
            if existing is None:
                async with self._agent_message_lock:
                    existing = (
                        self._conversation_persistence.find_dispatch(
                            dispatch_request_key=dispatch_request_key
                        )
                        if dispatch_request_key is not None
                        else None
                    )
                    if existing is None:
                        sender_user_id = self._conversation_persistence.agent_user_id(
                            agent_id=source_agent_id
                        )
                        if sender_user_id is None:
                            raise ValueError(
                                f"username not found: agent:{source_agent_id}"
                            )
                        # bugfix-404 fix-realtime: user-target notifications must flow
                        # through EventBridge so message.created is written to
                        # conversation_events and the front-end real-time stream picks it
                        # up without a manual refresh.  Agent-target messages go via the
                        # direct create_message + relay path unchanged — the target agent
                        # receives the content through the relay channel, not the WS stream.
                        #
                        # emit_instant_message is used instead of on_turn_start/on_message_completed
                        # because background notifications carry the full text upfront — no streaming
                        # phase.  message.created is emitted with final content + delivery_status=
                        # "completed" so the front-end renders the settled bubble immediately with no
                        # empty-window spinner (bugfix-404 reviewer feedback).
                        if (
                            resolved_target.kind in {"user_id", "conversation_id"}
                            and self._event_bridge is not None
                        ):
                            message = self._event_bridge.emit_instant_message(
                                conversation_id=conversation_id,
                                agent_user_id=sender_user_id,
                                agent_id=source_agent_id,
                                content=text,
                            )
                        else:
                            message = self._message_repository.create_message(
                                conversation_id=conversation_id,
                                sender_user_id=sender_user_id,
                                sender_type="agent",
                                content=text,
                            )
                        # The asyncio lock is process-local. The durable first write is
                        # the authority when another handler/process races this message.
                        owns_durable_dispatch = True
                        if dispatch_request_key is not None:
                            durable_dispatch = (
                                self._conversation_persistence.record_dispatch(
                                    AgentDispatchRecord(
                                        dispatch_request_key=dispatch_request_key,
                                        source_agent_id=source_agent_id,
                                        target_kind=resolved_target.kind,
                                        target_id=resolved_target.id,
                                        conversation_id=conversation_id,
                                        message_id=message.id,
                                    )
                                )
                            )
                            owns_durable_dispatch = (
                                durable_dispatch.message_id == message.id
                            )
                        if (
                            owns_durable_dispatch
                            and resolved_target.kind == "agent_id"
                            and self._relay_service is not None
                        ):
                            target_node_id = (
                                self._conversation_persistence.agent_node_id(
                                    agent_id=resolved_target.id
                                )
                            )
                            if target_node_id is not None:
                                _relay_result = self._relay_service.enqueue_message_relay(
                                    message=message,
                                    target_node_id=target_node_id,
                                    idempotency_key=f"agent-dm:{message.id}:{resolved_target.id}",
                                    sender_user_id=sender_user_id,
                                    conversation_type="direct",
                                    _override_agent_id=resolved_target.id,
                                )
                                if _relay_result.created:
                                    await self.push_relay_message(
                                        relay_task_id=_relay_result.relay_task.relay_task_id,
                                        target_node_id=target_node_id,
                                        payload=_relay_result.relay_task.payload,
                                    )
                        if not owns_durable_dispatch:
                            existing = durable_dispatch
                            conversation_id = durable_dispatch.conversation_id
                            resolved_target = DispatchTarget(
                                kind=durable_dispatch.target_kind,
                                id=durable_dispatch.target_id,
                            )
                            message_id = durable_dispatch.message_id
                    else:
                        conversation_id = existing.conversation_id
                        resolved_target = DispatchTarget(
                            kind=existing.target_kind,
                            id=existing.target_id,
                        )
                        message_id = existing.message_id
            else:
                conversation_id = existing.conversation_id
                resolved_target = DispatchTarget(
                    kind=existing.target_kind,
                    id=existing.target_id,
                )
                message_id = existing.message_id
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
        if self._conversation_persistence is None or self._message_repository is None:
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

            message = self._message_repository.create_message(
                conversation_id=conversation_id,
                sender_user_id=self._conversation_persistence.system_user_id(),
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
        if self._metrics_service is None or self._conversation_persistence is None:
            return
        if _optional_text(payload.get("status")) != "completed":
            return
        conversation_id = _optional_text(payload.get("conversation_id"))
        usage = _optional_usage(payload.get("usage"))
        if conversation_id is None or usage is None:
            return
        owner_id = self._conversation_persistence.conversation_usage_scope(
            conversation_id=conversation_id
        )
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
    # feat-439-M1: 缓存命中两字段(短键 cache_read / cache_total_input，由 gateway 白名单带出)。
    # 缺省(旧 gateway / 无缓存信息)→ 0，前端按「缓存命中 0 (0%)」空态渲染。
    cache_read_raw = value.get("cache_read")
    cache_read = max(int(cache_read_raw), 0) if isinstance(cache_read_raw, int) else 0
    cache_total_raw = value.get("cache_total_input")
    cache_total_input = (
        max(int(cache_total_raw), 0) if isinstance(cache_total_raw, int) else 0
    )
    return TokenUsage(
        output=max(completion, 0),
        context_used=max(prompt, 0),
        context_window=context_window,
        total=max(total, 0),
        cache_read_tokens=cache_read,
        cache_total_input_tokens=cache_total_input,
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
    reason = value.get("reason")
    detail = value.get("detail")
    emoji = value.get("emoji")
    approval = value.get("approval")
    return ToolCall(
        id=tc_id,
        name=name,
        status=status,  # type: ignore[arg-type]
        input=input_data,
        duration_ms=int(duration_ms) if isinstance(duration_ms, (int, float)) else None,
        output=str(output) if output is not None else None,
        reason=str(reason) if isinstance(reason, str) and reason else None,
        detail=detail if isinstance(detail, dict) else None,
        emoji=emoji if isinstance(emoji, str) and emoji else None,
        approval=str(approval) if isinstance(approval, str) and approval else None,
    )


def _not_registered_error(*, node_id: str) -> dict[str, object]:
    return {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": f"node {node_id} is not registered",
        },
    }
