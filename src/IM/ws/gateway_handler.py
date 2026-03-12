"""Gateway WebSocket connection manager for IM-SPEC §4."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from IM.application.relay_service import RelayService
from IM.infra.repositories import EventRepository, NodeRepository


@dataclass(frozen=True, slots=True)
class GatewayConnection:
    """Represent one active gateway websocket bound to a node id."""

    node_id: str
    websocket: WebSocket
    agents: list[str]
    capabilities: dict[str, object]
    reports: list[dict[str, object]]
    heartbeats: list[dict[str, object]]


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
    ) -> None:
        self._relay_service = relay_service
        self._node_repository = node_repository
        self._event_repository = event_repository
        self._lock = asyncio.Lock()
        self._connections: dict[str, GatewayConnection] = {}
        self._reports: list[dict[str, object]] = []

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
        return {
            "type": "error",
            "payload": {"code": "unsupported_message_type", "message": message_type},
        }

    async def push_relay_message(self, *, relay_task_id: str, target_node_id: str, payload: dict[str, object]) -> bool:
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

    async def push_config_sync(self, *, target_node_id: str, agent_id: str, profile_version: int) -> bool:
        """Push one config.sync notification to a connected gateway node."""
        return await self._push_downstream(
            target_node_id=target_node_id,
            message_type="config.sync",
            payload={"agent_id": agent_id, "profile_version": profile_version},
        )

    async def push_heartbeat_trigger(self, *, target_node_id: str, agent_id: str, reason: str) -> bool:
        """Push one heartbeat.trigger notification to a connected gateway node."""
        return await self._push_downstream(
            target_node_id=target_node_id,
            message_type="heartbeat.trigger",
            payload={"agent_id": agent_id, "reason": reason},
        )

    async def disconnect(self, *, node_id: str) -> None:
        """Remove one node from the active connection map."""
        async with self._lock:
            self._connections.pop(node_id, None)
        if self._node_repository is not None:
            self._node_repository.mark_disconnected(node_id=node_id)

    async def is_connected(self, *, node_id: str) -> bool:
        """Report whether one node currently has an active websocket."""
        async with self._lock:
            return node_id in self._connections

    async def snapshot_connection(self, *, node_id: str) -> GatewayConnection | None:
        """Return one tracked connection snapshot for tests and diagnostics."""
        async with self._lock:
            return self._connections.get(node_id)

    async def _handle_register(self, *, websocket: WebSocket, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        agents = _require_string_list(payload.get("agents", []), field_name="agents")
        capabilities = _require_dict(payload.get("capabilities", {}), field_name="capabilities")
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
        if self._node_repository is not None:
            self._node_repository.record_gateway_registration(
                node_id=node_id,
                node_name=node_name,
                version=version,
                agent_count=len(agents),
            )
        return {"type": "ack", "payload": {"message_type": "node.register", "node_id": node_id}}

    async def _handle_heartbeat(self, *, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.heartbeats.append(payload)
        if self._node_repository is not None:
            self._node_repository.record_heartbeat(
                node_id=node_id,
                reported_status=_optional_text(payload.get("status")),
                agent_count=_optional_int(payload.get("agent_count")),
                last_error=_optional_text(payload.get("last_error")),
                version=_optional_text(payload.get("version")),
            )
        return {"type": "ack", "payload": {"message_type": "node.heartbeat", "node_id": node_id}}

    async def _handle_report(self, *, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.reports.append(payload)
            self._reports.append(payload)
        self._persist_report_event(payload=payload)
        return {"type": "ack", "payload": {"message_type": "node.report", "node_id": node_id}}

    async def _handle_delivery_receipt(self, *, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        relay_task_id = _require_text(payload.get("relay_task_id"), field_name="relay_task_id")
        delivery_status = _require_text(payload.get("delivery_status"), field_name="delivery_status")
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
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.delivery_receipt",
                "node_id": node_id,
                "relay_task_id": relay_task_id,
                "status": task.status,
            },
        }

    async def _push_downstream(self, *, target_node_id: str, message_type: str, payload: dict[str, object]) -> bool:
        async with self._lock:
            connection = self._connections.get(target_node_id)
        if connection is None:
            return False
        await connection.websocket.send_json({"type": message_type, "payload": payload})
        return True

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

    def _persist_receipt_events(self, *, task, node_id: str, detail: str | None) -> None:  # noqa: ANN001
        if self._event_repository is None:
            return
        progress_map = {
            "sent": ("relay.accepted", "accepted", "accepted_by_gateway"),
            "completed": ("relay.completed", "completed", "agent_run_completed"),
            "failed": ("relay.failed", "failed", "agent_run_failed"),
        }
        event_type, progress_state, semantic = progress_map[task.receipt_status or task.status]
        payload = {
            "conversation_id": task.conversation_id,
            "message_id": task.message_id,
            "relay_task_id": task.relay_task_id,
            "target_node_id": task.target_node_id,
            "node_id": node_id,
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
        conversation_id = _require_text(payload.get("conversation_id"), field_name="conversation_id")
        message_id = _require_text(payload.get("message_id"), field_name="message_id")
        status = _require_text(payload.get("status"), field_name="status")
        summary = _optional_text(payload.get("summary"))
        run_id = _optional_text(payload.get("run_id"))
        guidance = _optional_text(payload.get("guidance"))
        progress_state = "processing" if status == "running" else ("completed" if status == "completed" else "failed")
        semantic = "agent_run_processing" if progress_state == "processing" else (
            "agent_run_completed" if progress_state == "completed" else "agent_run_failed"
        )
        self._event_repository.append_event(
            conversation_id=conversation_id,
            message_id=message_id,
            event_type="relay.processing" if progress_state == "processing" else "relay.report",
            delivery_status=status,
            payload={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "node_id": _require_text(payload.get("node_id"), field_name="node_id"),
                "run_id": run_id,
                "summary": summary,
                "status": status,
                "progress_state": progress_state,
                "semantic": semantic,
                "guidance": guidance,
            },
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
                    "guidance": guidance or "检查节点连接和执行日志后重试；如需要可重新发送消息。",
                    "notice_type": "action_required",
                },
            )
            self._event_repository.update_message_delivery_status(
                message_id=message_id,
                delivery_status="failed",
            )


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


def _not_registered_error(*, node_id: str) -> dict[str, object]:
    return {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": f"node {node_id} is not registered",
        },
    }
