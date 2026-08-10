"""Unit tests for gateway websocket connection management."""

import asyncio
import json
from pathlib import Path

import pytest

from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayService
from IM.domain.models import Message
from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import (
    GatewayConversationPersistence,
    GatewayNodePersistence,
)
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.metrics import UsageMetricsRepository
from IM.infra.repositories.users import UserRepository
from dataclasses import dataclass

from IM.application.event_bridge import EventBridge
from IM.infra.channel_control_store import ChannelControlStore
from IM.infra.repositories.config_boundaries import AgentConfigBoundaryRepository
from IM.infra.repositories.events import EventRepository
from IM.ws.gateway.channel_control import GatewayChannelControl
from IM.ws.gateway.control import GatewayControl
from IM.ws.gateway.execution import GatewayExecution
from IM.ws.gateway.relay import GatewayRelay
from IM.ws.gateway.runtime import GatewayRuntime
from IM.ws.gateway.sessions import GatewaySessions


@dataclass
class GatewayTestStack:
    """Concrete Gateway modules assembled for behavior-level unit tests."""

    runtime: GatewayRuntime
    sessions: GatewaySessions
    control: GatewayControl
    channel_control: GatewayChannelControl
    relay: GatewayRelay
    execution: GatewayExecution


def build_gateway(
    *,
    relay_service: RelayService,
    node_persistence=None,
    conversation_persistence=None,
    message_repository=None,
    boundary_repository=None,
    event_repository=None,
    metrics_service=None,
    user_stream_registry=None,
    event_bridge=None,
    channel_control_store=None,
    lock: asyncio.Lock | None = None,
) -> GatewayTestStack:
    """Assemble the same concrete Gateway graph as the application root."""
    lock = lock or asyncio.Lock()
    sessions = GatewaySessions(
        node_persistence=node_persistence,
        user_stream_registry=user_stream_registry,
        lock=lock,
    )
    execution = GatewayExecution(
        sessions=sessions,
        conversation_persistence=conversation_persistence,
        message_repository=message_repository,
        boundary_repository=boundary_repository,
        event_repository=event_repository,
        metrics_service=metrics_service,
        event_bridge=event_bridge,
        lock=lock,
    )
    control = GatewayControl(sessions=sessions, lock=lock)
    channel_control = GatewayChannelControl(
        sessions=sessions,
        channel_control_store=channel_control_store,
        lock=lock,
    )
    relay = GatewayRelay(
        sessions=sessions,
        execution=execution,
        relay_service=relay_service,
        conversation_persistence=conversation_persistence,
        message_repository=message_repository,
        event_repository=event_repository,
        lock=lock,
    )
    return GatewayTestStack(
        runtime=GatewayRuntime(
            sessions=sessions,
            control=control,
            channel_control=channel_control,
            relay=relay,
            execution=execution,
        ),
        sessions=sessions,
        control=control,
        channel_control=channel_control,
        relay=relay,
        execution=execution,
    )


class StubWebSocket:
    def __init__(self) -> None:
        self.sent_json: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent_json.append(payload)


class FailingWebSocket(StubWebSocket):
    async def send_json(self, payload: dict[str, object]) -> None:
        raise RuntimeError("socket closed")


def _build_handler(tmp_path: Path) -> GatewayTestStack:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return build_gateway(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=MessageRepository(connection),
    )


def _build_handler_with_node_persistence(
    tmp_path: Path,
) -> tuple[GatewayTestStack, object]:
    """构建带 node persistence seam 的 handler，用于验证 profile 落库行为。"""

    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    return (
        build_gateway(
            relay_service=RelayService(connection),
            metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
            conversation_persistence=GatewayConversationPersistence(connection),
            message_repository=MessageRepository(connection),
            node_persistence=GatewayNodePersistence(connection),
        ),
        connection,
    )


def test_register_heartbeat_and_report_track_connection_state(tmp_path: Path) -> None:
    """Record register/heartbeat/report payloads under one active node."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    register_ack = asyncio.run(
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.heartbeat",
            payload={"node_id": "node-1", "status": "online"},
        )
    )
    report_ack = asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.report",
            payload={"node_id": "node-1", "run_id": "run-1", "status": "completed"},
        )
    )
    snapshot = asyncio.run(handler.sessions.snapshot_connection(node_id="node-1"))

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


def test_report_after_disconnect_wins_shared_lock_is_not_registered(
    tmp_path: Path,
) -> None:
    """断连先取得 report 临界区时，后到的 report 被拒绝。"""

    async def _report_after_disconnect() -> dict[str, object]:
        connection = connect(tmp_path / "im.db")
        initialize_schema(connection)
        lock = asyncio.Lock()
        handler = build_gateway(relay_service=RelayService(connection), lock=lock)
        websocket = StubWebSocket()
        await handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
        await lock.acquire()
        disconnect_task = asyncio.create_task(
            handler.sessions.disconnect(node_id="node-1")
        )
        await asyncio.sleep(0)
        report_task = asyncio.create_task(
            handler.runtime.handle_message(
                websocket=websocket,
                message_type="node.report",
                payload={"node_id": "node-1", "run_id": "run-1", "status": "completed"},
            )
        )
        await asyncio.sleep(0)
        lock.release()
        response = await report_task
        await disconnect_task
        return response

    assert asyncio.run(_report_after_disconnect()) == {
        "type": "error",
        "payload": {
            "code": "node_not_registered",
            "message": "node node-1 is not registered",
        },
    }


def test_report_before_disconnect_keeps_legacy_ack_and_persistence(
    tmp_path: Path,
) -> None:
    """已取得 report 临界区的节点即使随后断连仍完成既有持久化和 ACK。"""

    async def _report_before_disconnect() -> tuple[dict[str, object], int]:
        connection = connect(tmp_path / "im.db")
        initialize_schema(connection)
        users = UserRepository(connection)
        owner = users.create_user(username="owner", display_name="Owner")
        agent = users.create_user(username="agent", display_name="Agent")
        conversation = ConversationRepository(connection).create_conversation(
            title="chat", participant_ids=[owner.id, agent.id]
        )
        message = MessageRepository(connection).create_message(
            conversation_id=conversation.id,
            sender_user_id=agent.id,
            sender_type="agent",
            content="placeholder",
        )
        lock = asyncio.Lock()
        handler = build_gateway(
            relay_service=RelayService(connection),
            conversation_persistence=GatewayConversationPersistence(connection),
            message_repository=MessageRepository(connection),
            event_repository=EventRepository(connection),
            lock=lock,
        )
        websocket = StubWebSocket()
        await handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
        payload = {
            "node_id": "node-1",
            "run_id": "run-1",
            "status": "completed",
            "agent_id": "agent",
            "conversation_id": conversation.id,
            "message_id": message.id,
        }
        persisted_before = connection.execute(
            "SELECT COUNT(*) AS count FROM conversation_events WHERE conversation_id = ?",
            (conversation.id,),
        ).fetchone()["count"]

        await lock.acquire()
        report_task = asyncio.create_task(
            handler.runtime.handle_message(
                websocket=websocket,
                message_type="node.report",
                payload=payload,
            )
        )
        await asyncio.sleep(0)
        disconnect_task = asyncio.create_task(
            handler.sessions.disconnect(node_id="node-1")
        )
        await asyncio.sleep(0)
        lock.release()
        response = await report_task
        await disconnect_task
        persisted = connection.execute(
            "SELECT COUNT(*) AS count FROM conversation_events WHERE conversation_id = ?",
            (conversation.id,),
        ).fetchone()["count"]
        return response, persisted - persisted_before

    response, persisted = asyncio.run(_report_before_disconnect())

    assert response == {
        "type": "ack",
        "payload": {"message_type": "node.report", "node_id": "node-1"},
    }
    assert persisted == 1


def test_register_parses_and_seeds_agent_skills_and_tool_allowlist(
    tmp_path: Path,
) -> None:
    """bugfix-467: WS handler parses agent_skills / agent_tool_allowlist into persistence."""
    handler, connection = _build_handler_with_node_persistence(tmp_path)
    websocket = StubWebSocket()

    ack = asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["agent-a"],
                "agent_workspaces": {"agent-a": "/work/a"},
                "agent_skills": {"agent-a": ["plan", "playwright"]},
                "agent_tool_allowlist": {"agent-a": ["read", "bash", "edit"]},
                "capabilities": {"relay": True},
            },
        )
    )

    assert ack == {
        "type": "ack",
        "payload": {"message_type": "node.register", "node_id": "node-1"},
    }
    profile = AgentProfileRepository(connection).get_profile(agent_id="agent-a")
    assert profile is not None
    assert profile.skills == ["plan", "playwright"]
    assert profile.tool_allowlist == ["read", "bash", "edit"]


def test_register_seed_normalizer_drops_invalid_items_but_keeps_valid_ones(
    tmp_path: Path,
) -> None:
    """bugfix-467 fix-r1: mixed-type seed items filter per-item, not per-agent."""
    handler, connection = _build_handler_with_node_persistence(tmp_path)
    websocket = StubWebSocket()

    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["agent-a", "agent-b"],
                "agent_workspaces": {"agent-a": "/work/a", "agent-b": "/work/b"},
                "agent_skills": {
                    "agent-a": ["plan", 123, "playwright"],
                    "agent-b": [456, 789],
                },
                "agent_tool_allowlist": {
                    "agent-a": ["read", None, "bash"],
                    "agent-b": [{}, []],
                },
                "capabilities": {"relay": True},
            },
        )
    )

    profiles = AgentProfileRepository(connection)
    a = profiles.get_profile(agent_id="agent-a")
    b = profiles.get_profile(agent_id="agent-b")
    assert a is not None
    assert a.skills == ["plan", "playwright"]
    assert a.tool_allowlist == ["read", "bash"]
    assert b is not None
    assert b.skills == []
    assert b.tool_allowlist == []


def test_unknown_node_receives_not_registered_error(tmp_path: Path) -> None:
    """Reject heartbeat frames from nodes that never registered."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    response = asyncio.run(
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )

    assert asyncio.run(handler.sessions.is_connected(node_id="node-1")) is True
    asyncio.run(handler.sessions.disconnect(node_id="node-1"))
    assert asyncio.run(handler.sessions.is_connected(node_id="node-1")) is False


def test_request_agent_config_timeout_returns_none_for_connected_gateway(
    tmp_path: Path,
) -> None:
    """Fall back when a connected gateway does not answer a live config request."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    async def _request_without_reply() -> dict[str, object] | None:
        await handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["agent-a"], "capabilities": {}},
        )
        return await handler.control.request_agent_config(
            target_node_id="node-1",
            agent_id="agent-a",
            timeout_seconds=0,
        )

    result = asyncio.run(_request_without_reply())

    assert result is None
    assert websocket.sent_json[-1]["type"] == "agent.config.get"
    assert websocket.sent_json[-1]["payload"]["agent_id"] == "agent-a"


def test_distill_prompt_waiter_accepts_only_the_target_gateway_result(
    tmp_path: Path,
) -> None:
    """A same request id from another node cannot produce a local-path prompt."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()

    async def _request_and_correlate() -> dict[str, object] | None:
        await handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["agent-a"], "capabilities": {}},
        )
        request = asyncio.create_task(
            handler.control.request_distill_prompt(
                target_node_id="node-1",
                sources=[{"conversation_id": "conv-1", "source_agent_id": "agent-a"}],
                execution_agent_id="agent-a",
                target_scope="agent",
                timeout_seconds=0.5,
            )
        )
        await asyncio.sleep(0)
        request_id = websocket.sent_json[-1]["payload"]["request_id"]
        assert isinstance(request_id, str)
        await handler.control._handle_distill_prompt(  # noqa: SLF001 - drive correlation seam
            payload={
                "request_id": request_id,
                "node_id": "node-2",
                "prompt": "wrong gateway",
            }
        )
        assert not request.done()
        await handler.control._handle_distill_prompt(  # noqa: SLF001 - drive correlation seam
            payload={
                "request_id": request_id,
                "node_id": "node-1",
                "prompt": "local gateway",
            }
        )
        return await request

    assert asyncio.run(_request_and_correlate()) == {"prompt": "local gateway"}
    assert websocket.sent_json[-1]["type"] == "node.distill.prompt.request"


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
        handler.runtime.handle_message(
            websocket=old_websocket,
            message_type="node.register",
            payload=register_payload,
        )
    )
    asyncio.run(
        handler.runtime.handle_message(
            websocket=new_websocket,
            message_type="node.register",
            payload=register_payload,
        )
    )

    asyncio.run(
        handler.sessions.disconnect(node_id="node-1", expected_websocket=old_websocket)
    )

    snapshot = asyncio.run(handler.sessions.snapshot_connection(node_id="node-1"))
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
    handler = build_gateway(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=metrics_repo),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=messages_repo,
    )
    websocket = StubWebSocket()
    owner = users.create_user(username="owner", display_name="Owner")
    agent = users.create_user(username="agent-a", display_name="Agent A")
    conversation = conversations.create_conversation(
        title="chat", participant_ids=[owner.id, agent.id]
    )

    asyncio.run(
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )

    delivered = asyncio.run(
        handler.relay.push_relay_message(
            relay_task_id="relay-1",
            target_node_id="node-1",
            payload={"message": {"content": "hello"}},
        )
    )

    assert delivered is False
    assert asyncio.run(handler.sessions.is_connected(node_id="node-1")) is False


def test_completed_group_reply_broadcasts_background_context_to_peer_agents(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    relay_service = RelayService(connection)
    handler = build_gateway(
        relay_service=relay_service,
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=MessageRepository(connection),
    )
    websocket = StubWebSocket()
    owner = users.create_user(username="owner", display_name="Owner")
    agent_a_user = users.create_user(username="agent:A", display_name="A")
    agent_q_user = users.create_user(username="agent:Q", display_name="Q")
    conversation = conversations.create_conversation(
        title="group", participant_ids=[owner.id, agent_a_user.id, agent_q_user.id]
    )
    connection.execute(
        "INSERT INTO agent_profiles(agent_id, owner_id, node_id, display_name, description, custom_prompt, skills_json, tool_allowlist_json, group_reply_policy, default_model, workspace_root, profile_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
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
        "INSERT INTO agent_profiles(agent_id, owner_id, node_id, display_name, description, custom_prompt, skills_json, tool_allowlist_json, group_reply_policy, default_model, workspace_root, profile_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
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
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
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


def test_suppressed_group_reply_is_not_broadcast_to_peer_agents(
    tmp_path: Path,
) -> None:
    """A completed NO_REPLY receipt must stop before creating any peer relay task."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    profiles = AgentProfileRepository(connection)
    relay_service = RelayService(connection)
    handler = build_gateway(
        relay_service=relay_service,
        conversation_persistence=GatewayConversationPersistence(connection),
    )
    websocket = StubWebSocket()
    owner = users.create_user(username="owner", display_name="Owner")
    agent = users.create_user(username="agent:A", display_name="A")
    peer = users.create_user(username="agent:Q", display_name="Q")
    for agent_id in ("A", "Q"):
        profiles.upsert_profile(
            agent_id=agent_id,
            owner_id=owner.owner_id,
            node_id="node-1",
            display_name=agent_id,
            description="test agent",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="MENTION",
            default_model=None,
            workspace_root=f"/work/{agent_id}",
        )
    conversation = ConversationRepository(connection).create_conversation(
        title="group", participant_ids=[owner.id, agent.id, peer.id]
    )
    message = MessageRepository(connection).create_message(
        conversation_id=conversation.id,
        sender_user_id=owner.id,
        sender_type="user",
        content="@agent:A hi",
    )
    task = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-1",
        idempotency_key="relay:no-reply",
        sender_user_id=owner.id,
        conversation_type="group",
        _override_agent_id="A",
    ).relay_task
    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["A", "Q"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.delivery_receipt",
            payload={
                "node_id": "node-1",
                "relay_task_id": task.relay_task_id,
                "delivery_status": "completed",
                "detail": "NO_REPLY",
            },
        )
    )

    assert response is not None
    assert response["type"] == "ack"
    count = connection.execute("SELECT COUNT(*) FROM relay_tasks").fetchone()[0]
    assert count == 1


def test_handle_agent_message_routes_user_target_and_persists_message(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages_repo = MessageRepository(connection)
    handler = build_gateway(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=messages_repo,
    )
    websocket = StubWebSocket()
    source_agent = users.create_user(username="agent:A", display_name="Agent A")
    teammate = users.create_user(username="teammate", display_name="Teammate")

    response = asyncio.run(
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
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
    handler = build_gateway(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=messages_repo,
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
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload=payload,
        )
    )
    second = asyncio.run(
        handler.runtime.handle_message(
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


def test_parse_token_usage_normalizes_totals_and_cache_fields() -> None:
    """Normalize both current usage payloads and legacy payloads without totals/cache."""
    from IM.ws.gateway.protocol import _parse_token_usage

    current = _parse_token_usage(
        {
            "prompt": 400,
            "completion": 15,
            "total": 415,
            "cache_read": 270,
            "cache_total_input": 400,
        }
    )
    legacy = _parse_token_usage({"prompt": 12, "completion": 30})

    assert current is not None
    assert current.total == 415
    assert current.cache_read_tokens == 270
    assert current.cache_total_input_tokens == 400
    assert legacy is not None
    assert legacy.total == 42
    assert legacy.cache_read_tokens == 0
    assert legacy.cache_total_input_tokens == 0


# ---------------------------------------------------------------------------
# feat-393: turn_start to_user_id 模式 — heartbeat canonical 直聊解析
# ---------------------------------------------------------------------------


def _build_handler_with_event_bridge(
    tmp_path: Path,
) -> tuple["GatewayTestStack", object, EventBridge]:
    """Build a GatewayTestStack with a real EventBridge wired to a FK-enforced DB.

    FK enforcement comes from initialize_schema which calls PRAGMA foreign_keys=ON.
    This is the guard against M138-style fake-green tests that used mocks bypassing FK.
    """
    from IM.application.event_bridge import EventBridge
    from IM.infra.repositories.events import EventRepository

    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    msg_repo = MessageRepository(connection)
    evt_repo = EventRepository(connection)
    bridge = EventBridge(message_repository=msg_repo, event_repository=evt_repo)
    handler = build_gateway(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=msg_repo,
        event_bridge=bridge,
    )
    return handler, connection, bridge


def test_streaming_delta_thinking_segment_persists_via_bridge(tmp_path: Path) -> None:
    """feat-439-M2 R3: kind=thinking_segment 经 gateway_handler 落到 message.thinking。"""
    handler, connection, bridge = _build_handler_with_event_bridge(tmp_path)
    users = UserRepository(connection)
    owner = users.create_user(username="nano", display_name="Nano")
    agent_user = users.create_user(username="agent:alpha", display_name="Alpha")
    connection.execute(
        "UPDATE users SET owner_id = ? WHERE id = ?", (owner.owner_id, agent_user.id)
    )
    connection.commit()
    conv = ConversationRepository(connection).create_conversation(
        title="t", participant_ids=[owner.id]
    )
    msg = bridge.on_turn_start(
        conversation_id=conv.id, agent_user_id=agent_user.id, agent_id="alpha"
    )

    response = asyncio.run(
        handler.runtime.handle_message(
            websocket=StubWebSocket(),
            message_type="node.streaming_delta",
            payload={
                "kind": "thinking_segment",
                "message_id": msg.id,
                "text": "先看 types.py",
                "run_id": "run-1",
            },
        )
    )
    assert response["type"] == "ack"
    assert response["payload"]["kind"] == "thinking_segment"

    final = MessageRepository(connection).list_messages(conversation_id=conv.id)[-1]
    assert final.thinking is not None
    assert [(s.seq, s.text) for s in final.thinking] == [(0, "先看 types.py")]


def test_turn_start_to_user_id_resolves_canonical_direct_conversation_and_creates_message(
    tmp_path: Path,
) -> None:
    """turn_start with to_user_id finds/creates the canonical (owner,agent) direct conv and persists a real message row.

    FK-enforced DB path: messages row must exist before events row is written.
    M138 fake-green guard: initialize_schema sets PRAGMA foreign_keys=ON; any synthetic FK would raise here.
    """
    handler, connection, _bridge = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    owner = users.create_user(username="nano", display_name="Nano")
    agent_user = users.create_user(username="agent:alpha", display_name="Alpha")

    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["alpha"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.runtime.handle_message(
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
    handler, connection, _bridge = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    owner = users.create_user(username="new-owner", display_name="New Owner")
    users.create_user(username="agent:beta", display_name="Beta")

    assert len(ConversationRepository(connection).list_conversations()) == 0

    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["beta"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.runtime.handle_message(
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

    handler, connection, _bridge = _build_handler_with_event_bridge(tmp_path)
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
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["gamma"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.runtime.handle_message(
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
    handler, connection, _bridge = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    convs = ConversationRepository(connection)
    owner = users.create_user(username="chat-owner", display_name="Chat Owner")
    agent_user = users.create_user(username="agent:delta", display_name="Delta")
    conv = convs.create_conversation(
        title="chat", participant_ids=[owner.id, agent_user.id]
    )

    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["delta"], "capabilities": {}},
        )
    )

    response = asyncio.run(
        handler.runtime.handle_message(
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
    handler, connection, _bridge = _build_handler_with_event_bridge(tmp_path)
    websocket = StubWebSocket()
    # Register agent user so agent lookup succeeds; owner user intentionally absent.
    users = UserRepository(connection)
    users.create_user(username="agent:epsilon", display_name="Epsilon")

    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": ["epsilon"], "capabilities": {}},
        )
    )

    nonexistent_owner_id = "00000000000000000000000000000000"
    response = asyncio.run(
        handler.runtime.handle_message(
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


def test_node_local_rpcs_return_none_when_node_is_offline(tmp_path: Path) -> None:
    """All workspace-backed controls fail at the Gateway RPC boundary when offline."""
    handler = _build_handler(tmp_path)

    heartbeat = asyncio.run(
        handler.control.request_node_heartbeat_md(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            timeout_seconds=0.1,
        )
    )

    cron_jobs = asyncio.run(
        handler.control.request_node_cron_jobs(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            timeout_seconds=0.1,
        )
    )

    skill_usage = asyncio.run(
        handler.control.request_node_skills_usage(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            timeout_seconds=0.1,
        )
    )

    cron_delete = asyncio.run(
        handler.control.request_node_cron_delete(
            target_node_id="offline-node",
            agent_id="agent-x",
            workspace_root="/fake/workspace",
            job_id="job-1",
            timeout_seconds=0.1,
        )
    )

    assert heartbeat is None
    assert cron_jobs is None
    assert skill_usage is None
    assert cron_delete is None


# ---------------------------------------------------------------------------
# heartbeat schema 防回归（feat-394）
# ---------------------------------------------------------------------------


def test_heartbeat_json_persisted_and_readable(tmp_path) -> None:
    """update_profile persists heartbeat_json; GET reads back same value."""
    import json
    from IM.infra.db import connect, initialize_schema
    from IM.infra.repositories.agents import AgentProfileRepository

    db = connect(tmp_path / "hb_persist.db")
    initialize_schema(db)

    repo = AgentProfileRepository(db)
    repo.upsert_profile(
        agent_id="agent-hb",
        owner_id="owner-1",
        node_id=None,
        display_name="HB Agent",
        description="",
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


# ---------------------------------------------------------------------------
# bugfix-404-M2 R1: _handle_register 种子落库三场景
# ---------------------------------------------------------------------------


def test_handle_register_with_agent_workspaces_seeds_first_seen_profile(
    tmp_path: Path,
) -> None:
    """首次注册时，若帧携带 agent_workspaces，则用上报值落库（而非凭空填 managed default）。

    bugfix-404-M2 决策 3：种子链路修复——IM 首次见到 agent 时用上报值，不再凭空填默认路径。
    """
    handler, connection = _build_handler_with_node_persistence(tmp_path)
    ws_path = "/worktrees/bugfix-404-M2/.gateway-workspace/Arch"
    asyncio.run(
        handler.runtime.handle_message(
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
    row = connection.execute(
        "SELECT workspace_root FROM agent_profiles WHERE agent_id = ?", ("Arch",)
    ).fetchone()
    assert row is not None
    assert row["workspace_root"] == ws_path, (
        f"首次注册时 workspace_root 应为上报值 {ws_path!r}，实际为 {row['workspace_root']!r}"
    )


def test_handle_register_runtime_profile_provisions_agent_user(
    tmp_path: Path,
) -> None:
    """Runtime node.register profiles must be usable as conversation participants."""
    handler, connection = _build_handler_with_node_persistence(tmp_path)

    asyncio.run(
        handler.runtime.handle_message(
            websocket=StubWebSocket(),
            message_type="node.register",
            payload={
                "node_id": "node-1",
                "agents": ["default-agent"],
                "capabilities": {},
            },
        )
    )

    users = UserRepository(connection)
    agent_user = users.get_user_by_username(username="agent:default-agent")
    assert agent_user is not None
    assert agent_user.display_name == "default-agent"


def test_handle_register_preserves_existing_workspace_on_reregister(
    tmp_path: Path,
) -> None:
    """已存在 profile 时，即使帧携带不同 agent_workspaces，也保持 DB 中的既有值（幂等语义）。

    bugfix-404-M2 决策 3：首见才写种子，已存在则不动（与 feat-379-M6 同模式）。
    """
    handler, connection = _build_handler_with_node_persistence(tmp_path)
    original_ws = "/original/workspace/Arch"
    new_ws = "/different/workspace/Arch"
    # 首次注册，确立原始值
    asyncio.run(
        handler.runtime.handle_message(
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
        handler.runtime.handle_message(
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
    row = connection.execute(
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
    handler, connection = _build_handler_with_node_persistence(tmp_path)
    asyncio.run(
        handler.runtime.handle_message(
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
    row = connection.execute(
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
) -> tuple["GatewayTestStack", object, list]:
    """Build a GatewayTestStack with repositories wired to a notify-collecting list.

    The notify list captures every ConversationEvent produced so tests can assert
    that message.created (not just message.sent/message.delivered) is emitted when
    a background agent sends a message to a human user.
    """
    from IM.application.event_bridge import EventBridge
    from IM.infra.repositories.events import EventRepository

    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    emitted: list = []
    msg_repo = MessageRepository(connection, notify=emitted.append)
    evt_repo = EventRepository(connection, notify=emitted.append)
    bridge = EventBridge(
        message_repository=msg_repo,
        event_repository=evt_repo,
    )
    handler = build_gateway(
        relay_service=RelayService(connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(connection)),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=msg_repo,
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
        handler.runtime.handle_message(
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


def test_agent_message_accepts_sidecar_only_and_rejects_both_empty(
    tmp_path: Path,
) -> None:
    """The shared agent.message wire is visible when text or a typed sidecar exists."""
    handler, connection, emitted = _build_handler_with_event_bridge_and_notify(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    users.create_user(username="agent:bg-agent", display_name="BG Agent")
    human = users.create_user(username="nano", display_name="Nano User")
    base = {
        "from_session_id": "bg-agent|tool_call:bg-sidecar",
        "to": f"user:{human.id}",
        "text": "",
    }

    accepted = asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload={
                **base,
                "background_returns": [
                    {
                        "task_id": "wt-1",
                        "task_type": "workflow",
                        "status": "completed",
                        "description": "review",
                        "workflow_run_id": "wf-1",
                        "result": "raw",
                    }
                ],
            },
        )
    )
    rejected = asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="agent.message",
            payload={**base, "from_session_id": "bg-agent|tool_call:bg-empty"},
        )
    )

    assert accepted["type"] == "ack"
    assert rejected["type"] == "error"
    assert rejected["payload"]["code"] == "invalid_agent_message"
    created = [event for event in emitted if event.event_type == "message.created"]
    assert len(created) == 1
    payload = json.loads(created[0].payload_json)
    assert payload["content"] == ""
    assert payload["background_returns"][0]["task_id"] == "wt-1"


def test_agent_message_replay_deduplicates_by_background_task_id(
    tmp_path: Path,
) -> None:
    """A Gateway replay with a new dispatch id cannot create a second task result."""
    handler, connection, emitted = _build_handler_with_event_bridge_and_notify(tmp_path)
    websocket = StubWebSocket()
    users = UserRepository(connection)
    users.create_user(username="agent:bg-agent", display_name="BG Agent")
    human = users.create_user(username="nano", display_name="Nano User")

    def send(dispatch_id: str):
        return asyncio.run(
            handler.runtime.handle_message(
                websocket=websocket,
                message_type="agent.message",
                payload={
                    "from_session_id": f"bg-agent|tool_call:{dispatch_id}",
                    "to": f"user:{human.id}",
                    "text": "done",
                    "background_returns": [
                        {
                            "task_id": "wt-replayed",
                            "task_type": "workflow",
                            "status": "completed",
                            "description": "review",
                            "result": "raw",
                        }
                    ],
                },
            )
        )

    first = send("dispatch-1")
    second = send("dispatch-2")

    assert first["payload"]["message_id"] == second["payload"]["message_id"]
    assert (
        len([event for event in emitted if event.event_type == "message.created"]) == 1
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
        handler.runtime.handle_message(
            websocket=websocket, message_type="agent.message", payload=payload
        )
    )
    first_event_count = len(emitted)

    second = asyncio.run(
        handler.runtime.handle_message(
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


def test_permission_response_frame_preserves_optional_reason(tmp_path: Path) -> None:
    """Permission frames preserve an explicit reason and normalize omission to empty."""
    handler = _build_handler(tmp_path)
    websocket = StubWebSocket()
    asyncio.run(
        handler.runtime.handle_message(
            websocket=websocket,
            message_type="node.register",
            payload={"node_id": "node-1", "agents": [], "capabilities": {}},
        )
    )

    explicit_delivered = asyncio.run(
        handler.control.push_permission_response(
            target_node_id="node-1",
            message_id="msg-1",
            request_id="req-1",
            decision="deny",
            reason="先别动这个文件",
        )
    )

    explicit_frame = next(
        f
        for f in websocket.sent_json
        if f.get("payload", {}).get("request_id") == "req-1"
    )
    omitted_delivered = asyncio.run(
        handler.control.push_permission_response(
            target_node_id="node-1",
            message_id="msg-1",
            request_id="req-2",
            decision="allow_once",
        )
    )
    omitted_frame = next(
        f
        for f in websocket.sent_json
        if f.get("payload", {}).get("request_id") == "req-2"
    )

    assert explicit_delivered is True
    assert omitted_delivered is True
    assert explicit_frame["payload"]["reason"] == "先别动这个文件"
    assert omitted_frame["payload"]["reason"] == ""
