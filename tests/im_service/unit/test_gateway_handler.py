"""Unit tests for gateway websocket connection management."""

import asyncio
from pathlib import Path

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.ws.gateway_handler import GatewayHandler


class StubWebSocket:
    def __init__(self) -> None:
        self.sent_json: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent_json.append(payload)


class FailingWebSocket(StubWebSocket):
    async def send_json(self, payload: dict[str, object]) -> None:
        raise RuntimeError("socket closed")


def _build_handler(tmp_path: Path) -> GatewayHandler:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return GatewayHandler(relay_service=RelayService(connection))


def test_register_heartbeat_and_report_track_connection_state(tmp_path: Path) -> None:
    """Record register/heartbeat/report payloads under one active node."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    register_ack = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["agent-a"], "capabilities": {"relay": True}},
        )
    )
    heartbeat_ack = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.heartbeat",
            payload={"node_id": "node-1", "status": "online"},
        )
    )
    report_ack = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.report",
            payload={"node_id": "node-1", "run_id": "run-1", "status": "completed"},
        )
    )
    snapshot = asyncio.run(handler.snapshot_connection(node_id="node-1"))

    assert register_ack == {"type": "ack", "payload": {"message_type": "node.register", "node_id": "node-1"}}
    assert heartbeat_ack == {"type": "ack", "payload": {"message_type": "node.heartbeat", "node_id": "node-1"}}
    assert report_ack == {"type": "ack", "payload": {"message_type": "node.report", "node_id": "node-1"}}
    assert snapshot is not None
    assert snapshot.node_id == "node-1"
    assert snapshot.heartbeats == [{"node_id": "node-1", "status": "online"}]
    assert snapshot.reports == [{"node_id": "node-1", "run_id": "run-1", "status": "completed"}]


def test_unknown_node_receives_not_registered_error(tmp_path: Path) -> None:
    """Reject heartbeat frames from nodes that never registered."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.heartbeat",
            payload={"node_id": "missing", "status": "online"},
        )
    )

    assert response == {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": "node missing is not registered",
        },
    }


def test_disconnect_removes_active_connection(tmp_path: Path) -> None:
    """Drop active node mapping when websocket disconnect cleanup runs."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()
    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )

    assert asyncio.run(handler.is_connected(node_id="node-1")) is True
    asyncio.run(handler.disconnect(node_id="node-1"))
    assert asyncio.run(handler.is_connected(node_id="node-1")) is False


def test_push_relay_message_returns_false_when_socket_send_fails(tmp_path: Path) -> None:
    """Treat broken websocket deliveries like disconnected nodes instead of bubbling 500s."""
    handler = _build_handler(tmp_path)
    websocket = FailingWebSocket()
    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )

    delivered = asyncio.run(
        handler.push_relay_message(
            relay_task_id="relay-1",
            target_node_id="node-1",
            payload={"message": {"content": "hello"}},
        )
    )

    assert delivered is False
    assert asyncio.run(handler.is_connected(node_id="node-1")) is False
