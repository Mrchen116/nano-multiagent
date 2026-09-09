"""Peer inputs are identified by committed assistant output, never relay receipts."""

import asyncio

from IM.application.event_bridge import EventBridge
from IM.application.relay_service import RelayService
from IM.domain.models import ReplyProcessItem
from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import GatewayConversationPersistence
from IM.infra.repositories.events import EventRepository
from IM.infra.repositories.messages import MessageRepository
from tests.im_service.unit.test_gateway_handler import StubWebSocket, build_gateway
from tests.im_service.unit.test_gateway_routing_freshness import _seed_nonlexical_group


def _setup(tmp_path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    conversation = _seed_nonlexical_group(connection)
    messages = MessageRepository(connection)
    relay_service = RelayService(connection)
    events = EventRepository(connection)
    bridge = EventBridge(message_repository=messages, event_repository=events)
    gateway = build_gateway(
        relay_service=relay_service,
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=messages,
        event_repository=events,
        event_bridge=bridge,
    )
    sockets = {}
    for agent, node in (("S", "node-source"), ("Z", "node-z-old"), ("A", "node-a-old")):
        socket = StubWebSocket()
        sockets[agent] = socket
        asyncio.run(
            gateway.runtime.handle_message(
                websocket=socket,
                message_type="node.register",
                payload={"node_id": node, "agents": [agent], "capabilities": {}},
            )
        )
    return gateway, messages, relay_service, bridge, conversation, sockets


def test_committed_output_fans_out_once_despite_consumed_follower_receipts(tmp_path):
    gateway, messages, relay_service, bridge, conversation, sockets = _setup(tmp_path)
    inputs = [
        messages.create_message(
            conversation_id=conversation.id,
            sender_user_id="owner-id",
            content=f"input {i}",
        )
        for i in range(3)
    ]
    tasks = [
        relay_service.enqueue_message_relay(
            message=message,
            target_node_id="node-source",
            idempotency_key=f"input:{message.id}",
            sender_user_id="owner-id",
            conversation_type="group",
            _override_agent_id="S",
        ).relay_task
        for message in inputs
    ]
    draft = bridge.on_turn_start(
        conversation_id=conversation.id, agent_user_id="source-id", agent_id="S"
    )
    bridge.on_reply_process(
        message_id=draft.id,
        item=ReplyProcessItem(item_id="d1", run_id="run", kind="draft", text="1"),
    )

    async def frame(kind, **fields):
        return await gateway.runtime.handle_message(
            websocket=sockets["S"],
            message_type="node.streaming_delta",
            payload={"kind": kind, **fields},
        )

    asyncio.run(frame("message_completed", message_id=draft.id, final_content=""))
    output = bridge.on_turn_start(
        conversation_id=conversation.id, agent_user_id="source-id", agent_id="S"
    )
    asyncio.run(frame("message_completed", message_id=output.id, final_content="2"))
    for task in tasks:
        asyncio.run(
            gateway.runtime.handle_message(
                websocket=sockets["S"],
                message_type="node.delivery_receipt",
                payload={
                    "node_id": "node-source",
                    "relay_task_id": task.relay_task_id,
                    "delivery_status": "completed",
                    "detail": "2",
                },
            )
        )
    asyncio.run(frame("message_completed", message_id=output.id, final_content="2"))
    for peer in ("Z", "A"):
        peer_frames = [
            frame
            for frame in sockets[peer].sent_json
            if frame["type"] == "relay.message"
        ]
        assert len(peer_frames) == 1
        payload = peer_frames[0]["payload"]
        assert payload["message"]["id"] == output.id
        assert payload["message"]["content"] == "2"
        assert payload["message"]["created_at"] == output.created_at
        assert payload["metadata"]["source_agent_id"] == "S"
        assert payload["agent_id"] == peer
        assert "background_context_only" not in payload["metadata"]
        asyncio.run(
            gateway.runtime.handle_message(
                websocket=sockets[peer],
                message_type="node.delivery_receipt",
                payload={
                    "node_id": "node-z-old" if peer == "Z" else "node-a-old",
                    "relay_task_id": payload["relay_task_id"],
                    "delivery_status": "failed",
                    "detail": "peer failed",
                },
            )
        )
    assert messages.get_message(message_id=output.id).delivery_status == "completed"


def test_group_tool_outputs_fan_out_by_committed_id_including_identical_text(tmp_path):
    gateway, messages, relay_service, bridge, conversation, sockets = _setup(tmp_path)

    def send(call_id):
        return asyncio.run(
            gateway.runtime.handle_message(
                websocket=sockets["S"],
                message_type="agent.message",
                payload={
                    "from_session_id": f"S|tool_call:{call_id}",
                    "to": f"conversation:{conversation.id}",
                    "text": "2",
                },
            )
        )

    first = send("one")
    replay = send("one")
    second = send("two")
    assert first["payload"]["message_id"] == replay["payload"]["message_id"]
    assert first["payload"]["message_id"] != second["payload"]["message_id"]
    for peer in ("Z", "A"):
        peer_frames = [
            frame
            for frame in sockets[peer].sent_json
            if frame["type"] == "relay.message"
        ]
        assert [frame["payload"]["message"]["id"] for frame in peer_frames] == [
            first["payload"]["message_id"],
            second["payload"]["message_id"],
        ]
