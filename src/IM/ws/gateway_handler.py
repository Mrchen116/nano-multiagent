"""Gateway WebSocket connection manager for IM-SPEC §4."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from IM.application.relay_service import RelayService


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

    def __init__(self, *, relay_service: RelayService) -> None:
        self._relay_service = relay_service
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
        await connection.websocket.send_json(
            {
                "type": "relay.message",
                "payload": {**payload, "relay_task_id": relay_task_id},
            }
        )
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
        return {"type": "ack", "payload": {"message_type": "node.register", "node_id": node_id}}

    async def _handle_heartbeat(self, *, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.heartbeats.append(payload)
        return {"type": "ack", "payload": {"message_type": "node.heartbeat", "node_id": node_id}}

    async def _handle_report(self, *, payload: dict[str, object]) -> dict[str, object]:
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            connection = self._connections.get(node_id)
            if connection is None:
                return _not_registered_error(node_id=node_id)
            connection.reports.append(payload)
            self._reports.append(payload)
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


def _not_registered_error(*, node_id: str) -> dict[str, object]:
    return {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": f"node {node_id} is not registered",
        },
    }
