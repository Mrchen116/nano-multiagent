"""Behavior tests for enqueue-time Gateway node routing."""

from __future__ import annotations

import asyncio
from pathlib import Path

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import (
    AgentDispatchRecord,
    GatewayConversationPersistence,
    GatewayNodePersistence,
)
from IM.infra.repositories import MessageRepository
from IM.ws.gateway_handler import GatewayHandler


class _RecordingWebSocket:
    def __init__(self) -> None:
        self.sent_json: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent_json.append(payload)


class _RebindAfterDispatchPersistence(GatewayConversationPersistence):
    """Move the target after message/dispatch persistence but before enqueue."""

    def record_dispatch(self, record: AgentDispatchRecord) -> AgentDispatchRecord:
        stored = super().record_dispatch(record)
        self._connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-new", record.target_id),
        )
        self._connection.commit()
        return stored


def test_direct_dispatch_rebinds_to_latest_node_before_enqueue(tmp_path: Path) -> None:
    """A post-write agent rebind routes relay/push to the replacement node."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    old_ws = _RecordingWebSocket()
    new_ws = _RecordingWebSocket()
    persistence = _RebindAfterDispatchPersistence(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        node_persistence=GatewayNodePersistence(connection),
        conversation_persistence=persistence,
        message_repository=MessageRepository(connection),
    )
    asyncio.run(
        handler.handle_message(
            websocket=old_ws,
            message_type="node.register",
            payload={
                "node_id": "node-old",
                "agents": ["A", "B"],
                "capabilities": {},
            },
        )
    )
    asyncio.run(
        handler.handle_message(
            websocket=new_ws,
            message_type="node.register",
            payload={"node_id": "node-new", "agents": [], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=old_ws,
            message_type="agent.message",
            payload={
                "from_session_id": "A|tool_call:rebind-direct",
                "to": "agent:B",
                "text": "route after rebind",
            },
        )
    )

    assert response is not None and response["type"] == "ack"
    relay = connection.execute(
        "SELECT target_node_id, message_id FROM relay_tasks"
    ).fetchone()
    assert relay is not None
    assert relay["target_node_id"] == "node-new"
    assert relay["message_id"] == response["payload"]["message_id"]
    assert [frame["type"] for frame in old_ws.sent_json] == []
    assert [frame["type"] for frame in new_ws.sent_json] == ["relay.message"]
