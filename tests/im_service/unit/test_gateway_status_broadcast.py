"""Unit tests for GatewayHandler node/agent status broadcast (feat-340-M10)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    NodeRepository,
    UsageMetricsRepository,
    UserRepository,
)
from IM.ws.gateway_handler import GatewayHandler
from IM.ws.user_stream import UserStreamRegistry


class _StubGatewayWebSocket:
    """Echo websocket sufficient for GatewayHandler register/heartbeat protocol."""

    async def send_json(
        self, payload: dict[str, object]
    ) -> None:  # pragma: no cover - unused here
        pass


class _RecordingUserWebSocket:
    """Browser-side websocket stub that captures broadcast text frames."""

    def __init__(self) -> None:
        self.frames: list[dict[str, object]] = []

    async def send_text(self, text: str) -> None:
        self.frames.append(json.loads(text))


def _build(tmp_path: Path):  # noqa: ANN202
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    registry = UserStreamRegistry()
    nodes = NodeRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        node_repository=nodes,
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=ConversationRepository(connection),
        user_stream_registry=registry,
    )
    users = UserRepository(connection)
    return handler, nodes, registry, connection, users


def test_register_broadcasts_node_online_to_owner(tmp_path: Path) -> None:
    """First register from a node already bound to an owner emits node.status_changed: online."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    # Pre-bind node to owner — represents a node already provisioned via /im/v1/nodes flow.
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )

    assert len(browser.frames) == 1
    frame = browser.frames[0]
    assert frame["op"] == "event"
    assert frame["event_type"] == "node.status_changed"
    assert frame["data"]["node_id"] == "node-1"
    assert frame["data"]["status"] == "online"
    assert frame["data"]["seq"] == 1


def test_register_with_agents_broadcasts_per_agent_status_online(
    tmp_path: Path,
) -> None:
    """Agent-status events ride alongside node-status events when node flips online."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["agent-a", "agent-b"],
                "capabilities": {},
            },
        )
    )

    event_types = [f["event_type"] for f in browser.frames]
    assert event_types.count("node.status_changed") == 1
    assert event_types.count("agent.status_changed") == 2
    agent_ids = sorted(
        f["data"]["agent_id"]
        for f in browser.frames
        if f["event_type"] == "agent.status_changed"
    )
    assert agent_ids == ["agent-a", "agent-b"]
    for f in browser.frames:
        if f["event_type"] == "agent.status_changed":
            assert f["data"]["status"] == "online"


def test_heartbeat_with_same_status_does_not_rebroadcast(tmp_path: Path) -> None:
    """Stable-state heartbeats must not produce duplicate status frames."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )
    frames_after_register = len(browser.frames)

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.heartbeat",
            payload={"node_id": "node-1", "status": "online"},
        )
    )

    assert len(browser.frames) == frames_after_register, (
        "stable heartbeat must not broadcast"
    )


def test_heartbeat_flip_to_degraded_broadcasts(tmp_path: Path) -> None:
    """Heartbeat that flips status (e.g. last_error set) must broadcast new status."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )
    browser.frames.clear()

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.heartbeat",
            payload={"node_id": "node-1", "status": "online", "last_error": "boom"},
        )
    )

    # last_error sets status to "degraded" per _normalize_node_status
    flip_frames = [
        f for f in browser.frames if f["event_type"] == "node.status_changed"
    ]
    assert len(flip_frames) == 1
    assert flip_frames[0]["data"]["status"] != "online"


def test_disconnect_broadcasts_node_and_agents_offline(tmp_path: Path) -> None:
    """WS disconnect path flips node to offline and broadcasts offline frames."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["agent-a"], "capabilities": {}},
        )
    )
    browser.frames.clear()

    asyncio.run(handler.disconnect(node_id="node-1"))

    types = [f["event_type"] for f in browser.frames]
    assert "node.status_changed" in types
    assert "agent.status_changed" in types
    node_frame = next(
        f for f in browser.frames if f["event_type"] == "node.status_changed"
    )
    agent_frame = next(
        f for f in browser.frames if f["event_type"] == "agent.status_changed"
    )
    assert node_frame["data"]["status"] == "offline"
    assert agent_frame["data"]["status"] == "offline"
    assert agent_frame["data"]["agent_id"] == "agent-a"


def test_cross_owner_isolation_no_leak(tmp_path: Path) -> None:
    """Owner A's node activity must not deliver any frame to owner B's browser WS."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner_a = users.create_user(username="owner-a", display_name="Owner A")
    owner_b = users.create_user(username="owner-b", display_name="Owner B")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner_a.owner_id)
    nodes.upsert_node(node_id="node-2", node_name="N2", owner_id=owner_b.owner_id)

    ws_a = _RecordingUserWebSocket()
    ws_b = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner_a.owner_id, ws_a))
    asyncio.run(registry.add(owner_b.owner_id, ws_b))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["agent-a"], "capabilities": {}},
        )
    )

    assert len(ws_a.frames) > 0, "owner A should receive its own node event"
    assert ws_b.frames == [], "owner B must not see owner A's events"


def test_orphan_node_without_owner_does_not_broadcast(tmp_path: Path) -> None:
    """Nodes without bound owner have no audience — should not raise and should not broadcast."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    # No upsert_node beforehand → first register creates a row with owner_id None.
    owner = users.create_user(username="owner-a", display_name="Owner A")
    browser = _RecordingUserWebSocket()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(
        handler.handle_message(
            websocket=_StubGatewayWebSocket(),
            message_type="node.register",
            payload={"node_id": "orphan", "agents": [], "capabilities": {}},
        )
    )

    assert browser.frames == []
