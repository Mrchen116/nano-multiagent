"""Unit tests for gateway websocket connection management."""

import asyncio
from pathlib import Path

import pytest

from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.domain.models import Message
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    MessageRepository,
    UsageMetricsRepository,
    UserRepository,
)
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
    return GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=ConversationRepository(connection),
    )


def test_register_heartbeat_and_report_track_connection_state(tmp_path: Path) -> None:
    """Record register/heartbeat/report payloads under one active node."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    register_ack = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["agent-a"],
                "capabilities": {"relay": True},
            },
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

    assert register_ack == {
        "type": "ack",
        "payload": {"message_type": "node.register", "node_id": "node-1"},
    }
    assert heartbeat_ack == {
        "type": "ack",
        "payload": {"message_type": "node.heartbeat", "node_id": "node-1"},
    }
    assert report_ack == {
        "type": "ack",
        "payload": {"message_type": "node.report", "node_id": "node-1"},
    }
    assert snapshot is not None
    assert snapshot.node_id == "node-1"
    assert snapshot.heartbeats == [{"node_id": "node-1", "status": "online"}]
    assert snapshot.reports == [
        {"node_id": "node-1", "run_id": "run-1", "status": "completed"}
    ]


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


def test_completed_report_persists_real_usage_metrics(tmp_path: Path) -> None:
    """Store completed relay usage under the conversation owner and agent scope."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    metrics_repo = UsageMetricsRepository(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages_repo = MessageRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=metrics_repo),
        conversation_repository=conversations,
    )
    websocket = StubWebSocket()
    owner = users.create_user(username="owner", display_name="Owner")
    agent = users.create_user(username="agent-a", display_name="Agent A")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[owner.id, agent.id]
    )

    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": [agent.id],
                "capabilities": {"relay": True},
            },
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.report",
            payload={
                "node_id": "node-1",
                "run_id": "run-1",
                "status": "completed",
                "agent_id": agent.id,
                "conversation_id": conversation.id,
                "message_id": "msg-1",
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                },
            },
        )
    )

    owner_rows = metrics_repo.list_usage_metrics(owner_id=conversation.owner_id)
    conversation_rows = metrics_repo.list_usage_metrics(conversation_id=conversation.id)

    assert response == {
        "type": "ack",
        "payload": {"message_type": "node.report", "node_id": "node-1"},
    }
    assert len(owner_rows) == 3
    by_scope = {(row.scope, row.agent_id): row for row in owner_rows}
    assert by_scope[("owner", None)].prompt_tokens == 11
    assert by_scope[("owner", None)].completion_tokens == 7
    assert by_scope[("owner", None)].total_tokens == 18
    assert by_scope[("conversation", None)].conversation_id == conversation.id
    assert by_scope[("conversation", None)].turns == 1
    assert by_scope[("agent", agent.id)].agent_id == agent.id
    assert by_scope[("agent", agent.id)].total_tokens == 18
    assert len(conversation_rows) == 2


def test_push_relay_message_returns_false_when_socket_send_fails(
    tmp_path: Path,
) -> None:
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


def test_completed_group_reply_broadcasts_background_context_to_peer_agents(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    relay_service = RelayService(connection)
    handler = GatewayHandler(
        relay_service=relay_service,
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=conversations,
    )
    websocket = StubWebSocket()
    owner = users.create_user(username="owner", display_name="Owner")
    agent_a_user = users.create_user(username="agent:A", display_name="A")
    agent_q_user = users.create_user(username="agent:Q", display_name="Q")
    conversation = conversations.create_conversation(
        title="group", participant_ids=[owner.id, agent_a_user.id, agent_q_user.id]
    )
    connection.execute(
        "INSERT INTO agent_profiles(agent_id, owner_id, node_id, display_name, description, system_prompt, skills_json, tool_allowlist_json, group_reply_policy, default_model, workspace_root, profile_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        (
            "A",
            owner.owner_id,
            "node-1",
            "A",
            "desc",
            "prompt",
            "[]",
            "[]",
            "manual",
            None,
            "/tmp/A",
            1,
        ),
    )
    connection.execute(
        "INSERT INTO agent_profiles(agent_id, owner_id, node_id, display_name, description, system_prompt, skills_json, tool_allowlist_json, group_reply_policy, default_model, workspace_root, profile_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        (
            "Q",
            owner.owner_id,
            "node-1",
            "Q",
            "desc",
            "prompt",
            "[]",
            "[]",
            "manual",
            None,
            "/tmp/Q",
            1,
        ),
    )
    connection.execute(
        "INSERT INTO messages(id, conversation_id, sender_user_id, sender_type, content, attachments_json, delivery_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "msg-1",
            conversation.id,
            owner.id,
            "user",
            "@agent:A hi",
            "[]",
            "sent",
            "2026-03-19T00:00:00Z",
        ),
    )
    connection.commit()
    original = relay_service.enqueue_message_relay(
        message=Message(
            id="msg-1",
            conversation_id=conversation.id,
            sender_user_id=owner.id,
            sender_type="user",
            content="@agent:A hi",
            created_at="2026-03-19T00:00:00Z",
        ),
        target_node_id="node-1",
        idempotency_key="relay:msg-1:node-1:A",
        sender_user_id=owner.id,
        conversation_type="group",
        _override_agent_id="A",
    ).relay_task
    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["A", "Q"],
                "capabilities": {"relay": True},
            },
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.delivery_receipt",
            payload={
                "node_id": "node-1",
                "relay_task_id": original.relay_task_id,
                "delivery_status": "completed",
                "detail": "A reply",
            },
        )
    )

    # bugfix-358: agent reply fanout is now dumb routing — one group relay per peer,
    # idempotency_key=agent-reply:<source>:<peer>, content is bare reply text (no sender prefix
    # because Gateway adds [sender] itself), no background_context_only flag (Gateway decides
    # trigger vs buffer purely from mentioned_agent_ids + group_reply_policy).
    peer_tasks = connection.execute(
        "SELECT relay_task_id, payload_json, status FROM relay_tasks WHERE idempotency_key = ?",
        (f"agent-reply:{original.relay_task_id}:Q",),
    ).fetchall()
    assert response["type"] == "ack"
    assert len(peer_tasks) == 1
    assert peer_tasks[0]["status"] == "dispatched"
    assert "background_context_only" not in peer_tasks[0]["payload_json"]
    assert '"agent_id":"Q"' in peer_tasks[0]["payload_json"]
    assert '"content":"A reply"' in peer_tasks[0]["payload_json"]
    relay_frames = [
        item for item in websocket.sent_json if item.get("type") == "relay.message"
    ]
    assert len(relay_frames) == 1
    assert relay_frames[0]["payload"]["agent_id"] == "Q"


def test_resolve_send_message_target_handles_agent_user_and_conversation(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=conversations,
    )
    owner = users.create_user(username="owner", display_name="Owner")
    source_agent = users.create_user(username="agent:A", display_name="Agent A")
    target_agent = users.create_user(username="agent:B", display_name="Agent B")
    teammate = users.create_user(username="teammate", display_name="Teammate")
    group = conversations.create_conversation(
        title="group",
        participant_ids=[owner.id, source_agent.id, target_agent.id, teammate.id],
    )

    agent_target, agent_conversation_id = handler.resolve_send_message_target(
        source_agent_id="A",
        target="agent:B",
    )
    user_target, user_conversation_id = handler.resolve_send_message_target(
        source_agent_id="A",
        target=f"user:{teammate.id}",
    )
    group_target, landed_group_id = handler.resolve_send_message_target(
        source_agent_id="A",
        target=f"conversation:{group.id}",
    )

    landed_agent = conversations.get_conversation(conversation_id=agent_conversation_id)
    landed_user = conversations.get_conversation(conversation_id=user_conversation_id)

    assert agent_target.kind == "agent_id"
    assert agent_target.id == "B"
    assert landed_agent is not None
    assert landed_agent.type == "direct"
    assert landed_agent.direct_kind == "agent-agent"
    assert landed_agent.title == "Agent B"

    assert user_target.kind == "user_id"
    assert user_target.id == teammate.id
    assert landed_user is not None
    assert landed_user.type == "direct"
    assert landed_user.direct_kind == "user-agent"
    assert landed_user.title == "Agent A"

    assert group_target.kind == "conversation_id"
    assert landed_group_id == group.id


def test_resolve_send_message_target_reuses_existing_direct_conversation(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=conversations,
    )
    source_agent = users.create_user(username="agent:A", display_name="Agent A")
    target_agent = users.create_user(username="agent:B", display_name="Agent B")
    existing = conversations.create_conversation(
        title="existing direct",
        participant_ids=[source_agent.id, target_agent.id],
    )

    first_target, first_conversation_id = handler.resolve_send_message_target(
        source_agent_id="A",
        target="agent:B",
    )
    second_target, second_conversation_id = handler.resolve_send_message_target(
        source_agent_id="A",
        target="agent:B",
    )

    assert first_target.kind == "agent_id"
    assert second_target.kind == "agent_id"
    assert first_conversation_id == existing.id
    assert second_conversation_id == existing.id


def test_resolve_send_message_target_rejects_unknown_target(tmp_path: Path) -> None:
    handler = _build_handler(tmp_path)
    users = UserRepository(handler._conversation_repository._connection)  # noqa: SLF001
    users.create_user(username="agent:A", display_name="Agent A")

    with pytest.raises(ValueError, match="target not found"):
        handler.resolve_send_message_target(
            source_agent_id="A", target="missing-target"
        )


def test_handle_agent_message_routes_user_target_and_persists_message(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages_repo = MessageRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=conversations,
    )
    websocket = StubWebSocket()
    source_agent = users.create_user(username="agent:A", display_name="Agent A")
    teammate = users.create_user(username="teammate", display_name="Teammate")

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload={
                "from_session_id": "A",
                "to": f"user:{teammate.id}",
                "text": "hello teammate",
            },
        )
    )

    assert response is not None
    assert response["type"] == "ack"
    payload = response["payload"]
    assert payload["message_type"] == "agent.message"
    assert payload["target_kind"] == "user_id"
    conversation_id = str(payload["conversation_id"])
    message_id = str(payload["message_id"])

    landed_conversation = conversations.get_conversation(
        conversation_id=conversation_id
    )
    assert landed_conversation is not None
    assert landed_conversation.type == "direct"
    assert landed_conversation.direct_kind == "user-agent"
    assert landed_conversation.title == "Agent A"
    assert set(landed_conversation.participant_ids) == {source_agent.id, teammate.id}
    messages = messages_repo.list_messages(conversation_id=conversation_id)
    assert len(messages) == 1
    assert messages[0].id == message_id
    assert messages[0].content == "hello teammate"
    assert messages[0].sender_type == "agent"
    assert messages[0].sender is not None
    assert messages[0].sender.id == "A"


def test_handle_agent_message_returns_error_for_invalid_source(tmp_path: Path) -> None:
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload={
                "from_session_id": "unknown-source",
                "to": "conversation:missing",
                "text": "test",
            },
        )
    )

    assert response is not None
    assert response["type"] == "error"
    assert response["payload"]["code"] == "invalid_agent_message"


def test_handle_agent_message_deduplicates_same_dispatch_request(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages_repo = MessageRepository(connection)
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=conversations,
    )
    websocket = StubWebSocket()
    source_agent = users.create_user(username="agent:A", display_name="Agent A")
    target_agent = users.create_user(username="agent:B", display_name="Agent B")

    payload = {
        "from_session_id": "A|tool_call:tool-call-1",
        "to": "agent:B",
        "text": "hello B",
    }
    first = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload=payload,
        )
    )
    second = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload=payload,
        )
    )

    assert first is not None and second is not None
    assert first["type"] == "ack"
    assert second["type"] == "ack"
    assert first["payload"]["message_id"] == second["payload"]["message_id"]
    assert first["payload"]["conversation_id"] == second["payload"]["conversation_id"]
    landed = conversations.get_conversation(
        conversation_id=str(first["payload"]["conversation_id"])
    )
    assert landed is not None
    assert landed.type == "direct"
    assert landed.direct_kind == "agent-agent"
    assert set(landed.participant_ids) == {source_agent.id, target_agent.id}
    messages = messages_repo.list_messages(conversation_id=landed.id)
    assert len(messages) == 1
    assert messages[0].content == "hello B"


def test_parse_token_usage_preserves_total_field() -> None:
    """_parse_token_usage must surface the total (prompt+completion) so the chip shows real usage, not just completion."""
    from IM.ws.gateway_handler import _parse_token_usage

    parsed = _parse_token_usage({"prompt": 2428, "completion": 1, "total": 2429})
    assert parsed is not None
    # Total exposed for the chip; output stays = completion for backwards reads.
    assert parsed.total == 2429, (
        f"Expected total=2429 (prompt+completion), got {parsed!r}"
    )
    assert parsed.output == 1
    assert parsed.context_used == 2428


def test_parse_token_usage_derives_total_when_missing() -> None:
    """_parse_token_usage derives total = prompt + completion when not provided."""
    from IM.ws.gateway_handler import _parse_token_usage

    parsed = _parse_token_usage({"prompt": 12, "completion": 30})
    assert parsed is not None
    assert parsed.total == 42
