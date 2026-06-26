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


def _build_handler_with_node_repo(tmp_path: Path) -> GatewayHandler:
    """构建带 NodeRepository 的 handler，用于验证 agent profile 落库行为。"""
    from IM.infra.repositories import NodeRepository

    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=ConversationRepository(connection),
        node_repository=NodeRepository(connection),
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


def test_stale_disconnect_preserves_replacement_connection(tmp_path: Path) -> None:
    """Keep a newer websocket when delayed cleanup arrives from the replaced socket."""
    handler = _build_handler(tmp_path)
    old_websocket = StubWebSocket()
    new_websocket = StubWebSocket()
    register_payload = {
        "node_id": "node-1",
        "agents": [],
        "capabilities": {},
    }
    asyncio.run(
        handler.handle_message(
            websocket=old_websocket,
            message_type="node.register",
            payload=register_payload,
        )
    )
    asyncio.run(
        handler.handle_message(
            websocket=new_websocket,
            message_type="node.register",
            payload=register_payload,
        )
    )

    asyncio.run(handler.disconnect(node_id="node-1", expected_websocket=old_websocket))

    snapshot = asyncio.run(handler.snapshot_connection(node_id="node-1"))
    assert snapshot is not None
    assert snapshot.websocket is new_websocket


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


def test_parse_token_usage_reads_cache_hit_fields() -> None:
    """feat-439-M1: gateway streaming_delta 带缓存命中两字段时落入 domain TokenUsage。"""
    from IM.ws.gateway_handler import _parse_token_usage

    parsed = _parse_token_usage(
        {
            "prompt": 400,
            "completion": 15,
            "total": 415,
            "cache_read": 270,
            "cache_total_input": 400,
        }
    )
    assert parsed is not None
    assert parsed.cache_read_tokens == 270
    assert parsed.cache_total_input_tokens == 400


def test_parse_token_usage_cache_defaults_zero_when_absent() -> None:
    """无 cache 字段(旧 gateway)时默认 0，不丢其它字段。"""
    from IM.ws.gateway_handler import _parse_token_usage

    parsed = _parse_token_usage({"prompt": 12, "completion": 30})
    assert parsed is not None
    assert parsed.cache_read_tokens == 0
    assert parsed.cache_total_input_tokens == 0


# ---------------------------------------------------------------------------
# feat-393: turn_start to_user_id 模式 — heartbeat canonical 直聊解析
# ---------------------------------------------------------------------------


def _build_handler_with_event_bridge(tmp_path: Path) -> tuple["GatewayHandler", object]:
    """Build a GatewayHandler with a real EventBridge wired to a FK-enforced DB.

    FK enforcement comes from initialize_schema which calls PRAGMA foreign_keys=ON.
    This is the guard against M138-style fake-green tests that used mocks bypassing FK.
    """
    from IM.application.event_bridge import EventBridge
    from IM.infra.repositories import EventRepository

    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    msg_repo = MessageRepository(connection)
    evt_repo = EventRepository(connection)
    bridge = EventBridge(
        message_repository=msg_repo, event_repository=evt_repo, notify=None
    )
    # user_repository is auto-derived from conversation_repository._connection in GatewayHandler.__init__
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=ConversationRepository(connection),
        event_bridge=bridge,
    )
    return handler, connection


def test_turn_start_to_user_id_resolves_canonical_direct_conversation_and_creates_message(
    tmp_path: Path,
) -> None:
    """turn_start with to_user_id finds/creates the canonical (owner,agent) direct conv and persists a real message row.

    FK-enforced DB path: messages row must exist before events row is written.
    M138 fake-green guard: initialize_schema sets PRAGMA foreign_keys=ON; any synthetic FK would raise here.
    """
    handler, connection = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    owner = users.create_user(username="nano", display_name="Nano")
    agent_user = users.create_user(username="agent:alpha", display_name="Alpha")

    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["alpha"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.streaming_delta",
            payload={
                "kind": "turn_start",
                "to_user_id": owner.id,
                "agent_id": "alpha",
                "run_id": "run-heartbeat-1",
            },
        )
    )

    assert response["type"] == "ack"
    ack_payload = response["payload"]
    assert ack_payload["kind"] == "turn_start"
    message_id = ack_payload.get("message_id")
    assert message_id, (
        "turn_start ack must return message_id so gateway can store it in run_context_store"
    )
    conversation_id = ack_payload.get("conversation_id")
    assert conversation_id, (
        "turn_start ack must return conversation_id for heartbeat run context"
    )

    # Verify the canonical direct conversation and real message row exist in FK-enforced DB.
    conversations = ConversationRepository(connection)
    conv = conversations.get_conversation(conversation_id=str(conversation_id))
    assert conv is not None
    assert conv.type == "direct"
    assert conv.direct_kind == "user-agent"
    assert set(conv.participant_ids) == {owner.id, agent_user.id}

    messages = MessageRepository(connection).list_messages(conversation_id=conv.id)
    assert len(messages) == 1
    assert messages[0].id == str(message_id)
    assert messages[0].sender_type == "agent"


def test_turn_start_to_user_id_creates_direct_conversation_when_none_exists(
    tmp_path: Path,
) -> None:
    """turn_start with to_user_id auto-creates the canonical direct conversation when owner has no prior chat."""
    handler, connection = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    owner = users.create_user(username="new-owner", display_name="New Owner")
    users.create_user(username="agent:beta", display_name="Beta")

    assert len(ConversationRepository(connection).list_conversations()) == 0

    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["beta"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.streaming_delta",
            payload={
                "kind": "turn_start",
                "to_user_id": owner.id,
                "agent_id": "beta",
                "run_id": "run-heartbeat-2",
            },
        )
    )

    assert response["type"] == "ack"
    conversations_after = ConversationRepository(connection).list_conversations()
    assert len(conversations_after) == 1
    conv = conversations_after[0]
    assert conv.type == "direct"
    assert conv.direct_kind == "user-agent"


def test_turn_start_to_user_id_uses_oldest_conversation_when_multiple_exist(
    tmp_path: Path,
) -> None:
    """turn_start with to_user_id selects the canonical (oldest) direct conversation when owner has multiple."""
    import time

    handler, connection = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    convs = ConversationRepository(connection)
    owner = users.create_user(username="multi-owner", display_name="Multi Owner")
    agent_user = users.create_user(username="agent:gamma", display_name="Gamma")

    first_conv = convs.create_conversation(
        title="first-direct",
        participant_ids=[owner.id, agent_user.id],
    )
    time.sleep(0.01)  # ensure different created_at
    convs.create_conversation(
        title="second-direct",
        participant_ids=[owner.id, agent_user.id],
    )

    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["gamma"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.streaming_delta",
            payload={
                "kind": "turn_start",
                "to_user_id": owner.id,
                "agent_id": "gamma",
                "run_id": "run-heartbeat-3",
            },
        )
    )

    assert response["type"] == "ack"
    returned_conv_id = response["payload"].get("conversation_id")
    assert returned_conv_id == first_conv.id, (
        "must land on the oldest (canonical) direct conversation"
    )


def test_turn_start_conversation_id_mode_unchanged_normal_chat_path(
    tmp_path: Path,
) -> None:
    """turn_start with conversation_id follows the existing eager-bubble path (regression guard).

    Ensures the to_user_id branch does not interfere with normal chat eager placeholder behavior.
    """
    handler, connection = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    convs = ConversationRepository(connection)
    owner = users.create_user(username="chat-owner", display_name="Chat Owner")
    agent_user = users.create_user(username="agent:delta", display_name="Delta")
    conv = convs.create_conversation(
        title="chat", participant_ids=[owner.id, agent_user.id]
    )

    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["delta"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.streaming_delta",
            payload={
                "kind": "turn_start",
                "conversation_id": conv.id,
                "agent_id": "delta",
                "run_id": "run-chat-1",
            },
        )
    )

    assert response["type"] == "ack"
    msg_id = response["payload"].get("message_id")
    assert msg_id, "existing eager-bubble path must still return message_id immediately"
    # Verify real message row created (FK path unbroken for normal chat)
    messages = MessageRepository(connection).list_messages(conversation_id=conv.id)
    assert len(messages) == 1
    assert messages[0].id == str(msg_id)


def test_turn_start_to_user_id_owner_not_in_db_returns_skipped_ack_not_exception(
    tmp_path: Path,
) -> None:
    """turn_start with a to_user_id that does not exist in the DB must return a skipped ack, never raise.

    Root cause of feat-393 round-1 WS flap: _find_or_create_direct_conversation calls
    create_conversation with a nonexistent left_user_id; SQLite FK enforcement raises
    IntegrityError which propagated out of serve() and closed the connection — causing
    413 open/close cycles.

    The fix must stay per-handler (not a broad except in serve()) so that other frame
    types' real exceptions still surface.  This test uses a FK-enforced DB (foreign_keys=ON
    via initialize_schema) to ensure the FK violation path is exercised, not mocked away.
    """
    handler, connection = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    # Register agent user so agent lookup succeeds; owner user intentionally absent.
    users = UserRepository(connection)
    users.create_user(username="agent:epsilon", display_name="Epsilon")

    asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["epsilon"], "capabilities": {}},
        )
    )

    nonexistent_owner_id = "00000000000000000000000000000000"
    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="node.streaming_delta",
            payload={
                "kind": "turn_start",
                "to_user_id": nonexistent_owner_id,
                "agent_id": "epsilon",
                "run_id": "run-heartbeat-bad-owner",
            },
        )
    )

    # Must be a skipped ack, not an exception.  WS connection must stay alive.
    assert response["type"] == "ack"
    ack_payload = response["payload"]
    assert ack_payload.get("skipped") == "owner_unresolved", (
        f"Expected skipped='owner_unresolved' but got: {ack_payload!r}"
    )
    # No message rows must have been created (owner does not exist, nothing to deliver).
    all_convs = ConversationRepository(connection).list_conversations()
    assert all_convs == [], (
        "No conversation should have been created for a nonexistent owner"
    )


# ---------------------------------------------------------------------------
# feat-394-M13: gateway-side state via WS RPC
# ---------------------------------------------------------------------------


def test_request_node_heartbeat_md_returns_none_when_node_offline(
    tmp_path: Path,
) -> None:
    """Heartbeat-md RPC returns None when target node is not connected.

    feat-394-M13 (决策 G): IM must never directly read gateway workspace files.
    request_node_heartbeat_md is the RPC path; offline node → None (graceful).
    """
    handler = _build_handler(tmp_path)

    result = asyncio.run(
        handler.request_node_heartbeat_md(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            timeout_seconds=0.1,
        )
    )

    assert result is None


def test_handle_heartbeat_md_resolves_waiter(tmp_path: Path) -> None:
    """_handle_heartbeat_md resolves the matching future with content.

    feat-394-M13: gateway sends node.heartbeat.md back with {request_id, content}.
    The IM waiter must receive the content string.
    """
    handler = _build_handler(tmp_path)
    loop = asyncio.new_event_loop()
    try:
        future: asyncio.Future[str | None] = loop.create_future()

        async def _run() -> dict[str, object]:
            async with handler._lock:  # noqa: SLF001
                handler._heartbeat_md_waiters["req-hb-1"] = future  # noqa: SLF001
            return await handler._handle_heartbeat_md(  # noqa: SLF001
                payload={
                    "request_id": "req-hb-1",
                    "node_id": "node-1",
                    "content": "# HEARTBEAT\n- Watch server uptime",
                }
            )

        ack = loop.run_until_complete(_run())
    finally:
        loop.close()

    assert ack == {
        "type": "ack",
        "payload": {"message_type": "node.heartbeat.md", "request_id": "req-hb-1"},
    }
    assert future.result() == "# HEARTBEAT\n- Watch server uptime"


def test_handle_heartbeat_md_accepts_empty_content(tmp_path: Path) -> None:
    """Gateway may return empty string when HEARTBEAT.md does not exist yet."""
    handler = _build_handler(tmp_path)
    loop = asyncio.new_event_loop()
    try:
        future: asyncio.Future[str | None] = loop.create_future()

        async def _run() -> None:
            async with handler._lock:  # noqa: SLF001
                handler._heartbeat_md_waiters["req-hb-2"] = future  # noqa: SLF001
            await handler._handle_heartbeat_md(  # noqa: SLF001
                payload={"request_id": "req-hb-2", "node_id": "n1", "content": ""}
            )

        loop.run_until_complete(_run())
    finally:
        loop.close()

    assert future.result() == ""


def test_request_node_cron_jobs_returns_none_when_node_offline(
    tmp_path: Path,
) -> None:
    """Cron-jobs RPC returns None when target node is not connected.

    feat-394-M13: cron jobs list must be fetched from gateway via RPC, not read
    directly from the IM host filesystem.  Offline node → None (graceful).
    """
    handler = _build_handler(tmp_path)

    result = asyncio.run(
        handler.request_node_cron_jobs(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            timeout_seconds=0.1,
        )
    )

    assert result is None


def test_handle_cron_jobs_resolves_waiter_with_job_list(tmp_path: Path) -> None:
    """_handle_cron_jobs resolves the matching future with the job list payload.

    feat-394-M13: gateway sends node.cron.jobs back with {request_id, jobs:[...]}.
    """
    handler = _build_handler(tmp_path)
    loop = asyncio.new_event_loop()
    jobs_payload = [{"id": "job-1", "name": "tick", "schedule": {"kind": "every"}}]
    try:
        future: asyncio.Future[list | None] = loop.create_future()

        async def _run() -> dict[str, object]:
            async with handler._lock:  # noqa: SLF001
                handler._cron_jobs_waiters["req-cj-1"] = future  # noqa: SLF001
            return await handler._handle_cron_jobs(  # noqa: SLF001
                payload={
                    "request_id": "req-cj-1",
                    "node_id": "node-1",
                    "jobs": jobs_payload,
                }
            )

        ack = loop.run_until_complete(_run())
    finally:
        loop.close()

    assert ack == {
        "type": "ack",
        "payload": {"message_type": "node.cron.jobs", "request_id": "req-cj-1"},
    }
    assert future.result() == jobs_payload


def test_request_node_cron_delete_returns_none_when_node_offline(
    tmp_path: Path,
) -> None:
    """Cron-delete RPC returns None when target node is not connected.

    feat-394-M13: delete must also go via RPC, not direct file write on IM host.
    Offline node → None (graceful degradation); route layer maps to 503/404.
    """
    handler = _build_handler(tmp_path)

    result = asyncio.run(
        handler.request_node_cron_delete(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            job_id="job-1",
            timeout_seconds=0.1,
        )
    )

    assert result is None


def test_handle_cron_delete_resolves_waiter_with_deleted_flag(
    tmp_path: Path,
) -> None:
    """_handle_cron_delete resolves the future with deleted=True when job was found."""
    handler = _build_handler(tmp_path)
    loop = asyncio.new_event_loop()
    try:
        future: asyncio.Future[bool | None] = loop.create_future()

        async def _run() -> dict[str, object]:
            async with handler._lock:  # noqa: SLF001
                handler._cron_delete_waiters["req-cd-1"] = future  # noqa: SLF001
            return await handler._handle_cron_delete(  # noqa: SLF001
                payload={
                    "request_id": "req-cd-1",
                    "node_id": "node-1",
                    "deleted": True,
                }
            )

        ack = loop.run_until_complete(_run())
    finally:
        loop.close()

    assert ack == {
        "type": "ack",
        "payload": {"message_type": "node.cron.delete", "request_id": "req-cd-1"},
    }
    assert future.result() is True


def test_handle_cron_delete_resolves_waiter_with_not_found(tmp_path: Path) -> None:
    """Gateway returns deleted=False when job_id was not found in the file."""
    handler = _build_handler(tmp_path)
    loop = asyncio.new_event_loop()
    try:
        future: asyncio.Future[bool | None] = loop.create_future()

        async def _run() -> None:
            async with handler._lock:  # noqa: SLF001
                handler._cron_delete_waiters["req-cd-2"] = future  # noqa: SLF001
            await handler._handle_cron_delete(  # noqa: SLF001
                payload={
                    "request_id": "req-cd-2",
                    "node_id": "n1",
                    "deleted": False,
                }
            )

        loop.run_until_complete(_run())
    finally:
        loop.close()

    assert future.result() is False


# ---------------------------------------------------------------------------
# heartbeat schema 防回归（feat-394）
# ---------------------------------------------------------------------------


def test_heartbeat_json_field_present_in_agent_profile() -> None:
    """AgentProfile domain model must have heartbeat_json field (cadence data)."""
    from IM.domain.models import AgentProfile
    from dataclasses import fields

    field_names = {f.name for f in fields(AgentProfile)}
    assert "heartbeat_json" in field_names, "AgentProfile missing heartbeat_json field"


def test_heartbeat_json_column_in_agent_profiles_table(tmp_path) -> None:
    """agent_profiles table must have heartbeat_json column (DB migration guard)."""
    from IM.infra.db import connect, initialize_schema

    db_path = tmp_path / "hb_schema.db"
    conn = connect(db_path)
    initialize_schema(conn)

    cols = conn.execute("PRAGMA table_info(agent_profiles)").fetchall()
    col_names = {row["name"] for row in cols}
    assert "heartbeat_json" in col_names, (
        f"agent_profiles table missing heartbeat_json column; columns: {sorted(col_names)}"
    )


def test_heartbeat_json_persisted_and_readable(tmp_path) -> None:
    """update_profile persists heartbeat_json; GET reads back same value."""
    import json
    from IM.infra.db import connect, initialize_schema
    from IM.infra.repositories import AgentProfileRepository

    db = connect(tmp_path / "hb_persist.db")
    initialize_schema(db)

    repo = AgentProfileRepository(db)
    repo.upsert_profile(
        agent_id="agent-hb",
        owner_id="owner-1",
        node_id=None,
        display_name="HB Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=str(tmp_path / "ws-hb"),
    )

    hb_json_str = json.dumps({"enabled": True, "every": "30m"})
    updated = repo.update_profile(
        agent_id="agent-hb",
        profile_version=1,
        display_name="HB Agent",
        description="",
        system_prompt="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        # bugfix-404-M2: workspace_root removed from update_profile — immutable after creation
        heartbeat_json=hb_json_str,
    )
    assert updated.heartbeat_json == hb_json_str

    refetched = repo.get_profile(agent_id="agent-hb")
    assert refetched is not None
    assert refetched.heartbeat_json == hb_json_str


def test_update_profile_accepts_heartbeat_json_param() -> None:
    """AgentProfileRepository.update_profile must accept heartbeat_json parameter."""
    import inspect
    from IM.infra.repositories import AgentProfileRepository

    sig = inspect.signature(AgentProfileRepository.update_profile)
    assert "heartbeat_json" in sig.parameters, (
        "update_profile must accept heartbeat_json for cadence data"
    )


def test_update_request_and_response_have_heartbeat_json_field() -> None:
    """UpdateAgentConfigRequest and AgentConfigResponse must carry heartbeat_json."""
    from IM.api.routes.agents import UpdateAgentConfigRequest, AgentConfigResponse

    req_fields = UpdateAgentConfigRequest.model_fields
    resp_fields = AgentConfigResponse.model_fields
    assert "heartbeat_json" in req_fields, (
        "UpdateAgentConfigRequest missing heartbeat_json field"
    )
    assert "heartbeat_json" in resp_fields, (
        "AgentConfigResponse missing heartbeat_json field"
    )


# ---------------------------------------------------------------------------
# bugfix-404-M2 R1: _handle_register 种子落库三场景
# ---------------------------------------------------------------------------


def test_handle_register_with_agent_workspaces_seeds_first_seen_profile(
    tmp_path: Path,
) -> None:
    """首次注册时，若帧携带 agent_workspaces，则用上报值落库（而非凭空填 managed default）。

    bugfix-404-M2 决策 3：种子链路修复——IM 首次见到 agent 时用上报值，不再凭空填默认路径。
    """
    handler = _build_handler_with_node_repo(tmp_path)
    ws_path = "/worktrees/bugfix-404-M2/.gateway-workspace/Arch"
    asyncio.run(
        handler.handle_message(
            websocket=StubWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["Arch"],
                "capabilities": {},
                "agent_workspaces": {"Arch": ws_path},
            },
        )
    )
    conn = handler._node_repository._connection
    row = conn.execute(
        "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?", ("Arch",)
    ).fetchone()
    assert row is not None
    assert row["workspace_root"] == ws_path, (
        f"首次注册时 workspace_root 应为上报值 {ws_path!r}，实际为 {row['workspace_root']!r}"
    )


def test_handle_register_preserves_existing_workspace_on_reregister(
    tmp_path: Path,
) -> None:
    """已存在 profile 时，即使帧携带不同 agent_workspaces，也保持 DB 中的既有值（幂等语义）。

    bugfix-404-M2 决策 3：首见才写种子，已存在则不动（与 feat-379-M6 同模式）。
    """
    handler = _build_handler_with_node_repo(tmp_path)
    original_ws = "/original/workspace/Arch"
    new_ws = "/different/workspace/Arch"
    # 首次注册，确立原始值
    asyncio.run(
        handler.handle_message(
            websocket=StubWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["Arch"],
                "capabilities": {},
                "agent_workspaces": {"Arch": original_ws},
            },
        )
    )
    # 重新注册，携带不同 workspace（模拟断线重连）
    asyncio.run(
        handler.handle_message(
            websocket=StubWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["Arch"],
                "capabilities": {},
                "agent_workspaces": {"Arch": new_ws},
            },
        )
    )
    conn = handler._node_repository._connection
    row = conn.execute(
        "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?", ("Arch",)
    ).fetchone()
    assert row is not None
    assert row["workspace_root"] == original_ws, (
        f"重新注册时 workspace_root 应保持原值 {original_ws!r}，不应被覆盖为 {new_ws!r}"
    )


def test_handle_register_without_agent_workspaces_falls_back_to_managed_default(
    tmp_path: Path,
) -> None:
    """帧不含 agent_workspaces 字段时，退回旧行为：用 managed_workspace_root 填充。

    向后兼容性：老版本 gateway 发的帧无 agent_workspaces，IM 应走原路逻辑不报错。
    """
    handler = _build_handler_with_node_repo(tmp_path)
    asyncio.run(
        handler.handle_message(
            websocket=StubWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["LegacyAgent"],
                "capabilities": {},
                # 无 agent_workspaces 字段
            },
        )
    )
    conn = handler._node_repository._connection
    row = conn.execute(
        "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?",
        ("LegacyAgent",),
    ).fetchone()
    assert row is not None
    assert (
        row["workspace_root"] is not None and "LegacyAgent" in row["workspace_root"]
    ), "无 agent_workspaces 时应退回 managed default 路径，路径须含 agent_id"


# ---------------------------------------------------------------------------
# bugfix-404 fix-realtime: agent_message 对 user-target 产生 message.created 事件
# ---------------------------------------------------------------------------


def _build_handler_with_event_bridge_and_notify(
    tmp_path: Path,
) -> tuple["GatewayHandler", object, list]:
    """Build a GatewayHandler with EventBridge wired to a notify-collecting list.

    The notify list captures every ConversationEvent produced so tests can assert
    that message.created (not just message.sent/message.delivered) is emitted when
    a background agent sends a message to a human user.
    """
    from IM.application.event_bridge import EventBridge
    from IM.infra.repositories import EventRepository

    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    emitted: list = []
    msg_repo = MessageRepository(connection, notify=emitted.append)
    evt_repo = EventRepository(connection, notify=emitted.append)
    bridge = EventBridge(
        message_repository=msg_repo,
        event_repository=evt_repo,
        notify=emitted.append,
    )
    handler = GatewayHandler(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_repository=ConversationRepository(connection),
        event_bridge=bridge,
    )
    return handler, connection, emitted


def test_agent_message_user_target_emits_message_created_event(
    tmp_path: Path,
) -> None:
    """agent.message to a human user must produce a message.created conversation_event.

    bugfix-404 fix-realtime: the prior implementation called create_message directly,
    which only wrote message.sent/message.delivered — not message.created.  The front-end
    chat panel creates new bubbles exclusively on message.created, so without this event
    the message was invisible until a manual page refresh.

    This test proves the fix: agent.message to user_id → EventBridge path →
    message.created appears in conversation_events.
    """
    handler, connection, emitted = _build_handler_with_event_bridge_and_notify(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    users.create_user(username="agent:bg-agent", display_name="BG Agent")
    human = users.create_user(username="nano", display_name="Nano User")

    response = asyncio.run(
        handler.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload={
                "from_session_id": "bg-agent|tool_call:bg-task-1",
                "to": f"user:{human.id}",
                "text": "Background agent finished: here is your joke.",
            },
        )
    )

    assert response is not None
    assert response["type"] == "ack", f"Expected ack, got {response}"

    # The emitted events must include message.created (not only message.sent/delivered).
    event_types = [e.event_type for e in emitted]
    assert "message.created" in event_types, (
        f"agent.message to user must emit message.created for real-time delivery; "
        f"got only: {event_types}"
    )
    # And message.completed must close the turn so the bubble settles.
    assert "message.completed" in event_types, (
        f"agent.message to user must also emit message.completed to settle the bubble; "
        f"got: {event_types}"
    )
    # message.created must carry final content (not empty) so no empty-bubble window.
    import json

    created_event = next(e for e in emitted if e.event_type == "message.created")
    created_payload = json.loads(created_event.payload_json)
    assert (
        created_payload.get("content")
        == "Background agent finished: here is your joke."
    ), (
        "message.created payload must carry final text immediately — no empty-bubble window; "
        f"got content={created_payload.get('content')!r}"
    )
    assert created_payload.get("delivery_status") == "completed", (
        "message.created payload must carry delivery_status=completed for instant messages; "
        f"got {created_payload.get('delivery_status')!r}"
    )


def test_agent_message_user_target_dedup_does_not_double_emit(
    tmp_path: Path,
) -> None:
    """Sending the same dispatch_request_key twice must not create a second message.created.

    Idempotency invariant: gateway restarts can replay the same agent.message frame;
    only the first write produces events.  The second ack must return the same
    message_id without writing new conversation_events rows.
    """
    handler, connection, emitted = _build_handler_with_event_bridge_and_notify(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    users.create_user(username="agent:bg-agent", display_name="BG Agent")
    human = users.create_user(username="nano", display_name="Nano User")

    payload = {
        "from_session_id": "bg-agent|tool_call:bg-dedup-key",
        "to": f"user:{human.id}",
        "text": "Dedup test message",
    }

    first = asyncio.run(
        handler.handle_message(
            websocket=websocket, message_type="agent.message", payload=payload
        )
    )
    first_event_count = len(emitted)

    second = asyncio.run(
        handler.handle_message(
            websocket=websocket, message_type="agent.message", payload=payload
        )
    )

    assert first["type"] == "ack"
    assert second["type"] == "ack"
    assert first["payload"]["message_id"] == second["payload"]["message_id"], (
        "Dedup replay must return the same message_id"
    )
    # No new events must be emitted on the second call.
    assert len(emitted) == first_event_count, (
        f"Second agent.message replay emitted {len(emitted) - first_event_count} extra events; "
        f"expected 0 (idempotent)"
    )
