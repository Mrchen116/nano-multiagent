"""Unit tests for the heartbeat-timeout offline guard (feat-340-M10 R3)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
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
from IM.ws.user_stream import UserStreamRegistry, scan_and_flip_stale_nodes


class _RecordingWS:
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


def test_scan_flips_stale_online_node_to_offline_and_broadcasts(tmp_path: Path) -> None:
    """Nodes whose last_heartbeat_at predates the cutoff get flipped + broadcast."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingWS()
    asyncio.run(registry.add(owner.owner_id, browser))
    asyncio.run(
        handler.handle_message(
            websocket=type("X", (), {"send_json": lambda self, p: asyncio.sleep(0)})(),  # noqa: E501
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["agent-a"], "capabilities": {}},
        )
    )
    browser.frames.clear()

    # Force last_heartbeat_at older than timeout.
    stale_at = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat().replace("+00:00", "Z")
    connection.execute("UPDATE nodes SET last_heartbeat_at = ? WHERE node_id = ?", (stale_at, "node-1"))
    connection.commit()

    asyncio.run(scan_and_flip_stale_nodes(handler=handler, node_repository=nodes, timeout_seconds=60))

    offline_frames = [f for f in browser.frames if f["event_type"] == "node.status_changed"]
    assert len(offline_frames) == 1
    assert offline_frames[0]["data"]["status"] == "offline"
    assert offline_frames[0]["data"]["last_error"] == "heartbeat_timeout"
    snapshot = nodes.get_node(node_id="node-1")
    assert snapshot is not None
    assert snapshot.status == "offline"


def test_scan_skips_fresh_node(tmp_path: Path) -> None:
    """A node with a recent heartbeat is not touched."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)

    browser = _RecordingWS()
    asyncio.run(registry.add(owner.owner_id, browser))
    asyncio.run(
        handler.handle_message(
            websocket=type("X", (), {"send_json": lambda self, p: asyncio.sleep(0)})(),
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )
    browser.frames.clear()

    asyncio.run(scan_and_flip_stale_nodes(handler=handler, node_repository=nodes, timeout_seconds=60))

    assert browser.frames == []
    snapshot = nodes.get_node(node_id="node-1")
    assert snapshot is not None
    assert snapshot.status == "online"


def test_scan_idempotent_on_already_offline_node(tmp_path: Path) -> None:
    """Re-running the scan over an already-offline node is a no-op."""
    handler, nodes, registry, connection, users = _build(tmp_path)
    owner = users.create_user(username="owner-a", display_name="Owner A")
    nodes.upsert_node(node_id="node-1", node_name="N1", owner_id=owner.owner_id)
    # status defaults to offline via upsert_node when no register happened.

    browser = _RecordingWS()
    asyncio.run(registry.add(owner.owner_id, browser))

    asyncio.run(scan_and_flip_stale_nodes(handler=handler, node_repository=nodes, timeout_seconds=60))

    assert browser.frames == []
