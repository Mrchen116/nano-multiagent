"""User-stream tests for accepted external-channel status updates."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.infra.channel_control_store import ChannelControlStore
from IM.infra.channel_credentials import generate_channel_key_pair
from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import (
    GatewayConversationPersistence,
    GatewayNodePersistence,
)
from IM.infra.repositories import (
    AgentProfileRepository,
    MessageRepository,
    NodeRepository,
    UsageMetricsRepository,
)
from IM.ws.gateway_handler import GatewayHandler
from IM.ws.user_stream import UserStreamRegistry


class _GatewayWebSocket:
    async def send_json(self, _payload: dict[str, object]) -> None:
        pass


class _BrowserWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict[str, object]] = []

    async def send_text(self, text: str) -> None:
        self.frames.append(json.loads(text))


def test_accepted_status_broadcasts_precise_agent_channel_event_once(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "im.db"
    connection = connect(db_path)
    initialize_schema(connection)
    NodeRepository(connection).upsert_node(
        node_id="node-a", node_name="Node A", owner_id="owner-a", status="offline"
    )
    AgentProfileRepository(connection).upsert_profile(
        agent_id="agent-a",
        owner_id="owner-a",
        node_id="node-a",
        display_name="Agent A",
        description="",
        system_prompt="You are Agent A.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    pair = generate_channel_key_pair(private_seed=b"b" * 32)
    store = ChannelControlStore(db_path)
    store.register_node_public_key(
        owner_id="owner-a",
        node_id="node-a",
        key_id=pair.key_id,
        algorithm="X25519-HKDF-SHA256-AES-256-GCM",
        public_key=pair.public_key,
    )
    channel = store.create_channel(
        owner_id="owner-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_a"},
        secret={"app_secret": "secret"},
    ).channel
    registry = UserStreamRegistry()
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        node_persistence=GatewayNodePersistence(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=MessageRepository(connection),
        user_stream_registry=registry,
        channel_control_store=store,
    )
    gateway = _GatewayWebSocket()
    browser = _BrowserWebSocket()
    asyncio.run(registry.add("owner-a", browser))
    asyncio.run(
        handler.handle_message(
            websocket=gateway,
            message_type="node.register",
            payload={"node_id": "node-a", "agents": ["agent-a"], "capabilities": {}},
        )
    )
    browser.frames.clear()
    payload = {
        "request_id": "status-1",
        "node_id": "node-a",
        "channel_id": channel.channel_id,
        "channel_revision": 1,
        "runtime_incarnation": "inc-a",
        "status_sequence": 1,
        "instance_started": True,
        "connection_state": "connected",
        "diagnostics_state": "complete",
        "checks": [],
    }

    first = asyncio.run(
        handler.handle_message(
            websocket=gateway, message_type="channel.status", payload=payload
        )
    )
    duplicate = asyncio.run(
        handler.handle_message(
            websocket=gateway,
            message_type="channel.status",
            payload={**payload, "request_id": "status-2"},
        )
    )

    assert first["payload"]["outcome"] == "accepted"
    assert duplicate["payload"]["outcome"] == "already_current"
    assert browser.frames == [
        {
            "op": "event",
            "event_type": "agent.channel.status_changed",
            "data": {
                "seq": 3,
                "agent_id": "agent-a",
                "channel_id": channel.channel_id,
            },
        }
    ]

