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
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.ws.gateway.channel_control import GatewayChannelControl
from IM.ws.gateway.control import GatewayControl
from IM.ws.gateway.execution import GatewayExecution
from IM.ws.gateway.relay import GatewayRelay
from IM.ws.gateway.runtime import GatewayRuntime
from IM.ws.gateway.sessions import GatewaySessions


class _RecordingWebSocket:
    def __init__(self) -> None:
        self.sent_json: list[dict[str, object]] = []
        self._after_first_send = None

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent_json.append(payload)
        callback = self._after_first_send
        self._after_first_send = None
        if callback is not None:
            callback()


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


def _build_runtime(
    *,
    relay_service: RelayService,
    node_persistence: GatewayNodePersistence,
    conversation_persistence: GatewayConversationPersistence,
    message_repository: MessageRepository,
) -> GatewayRuntime:
    lock = asyncio.Lock()
    sessions = GatewaySessions(node_persistence=node_persistence, lock=lock)
    execution = GatewayExecution(
        sessions=sessions,
        conversation_persistence=conversation_persistence,
        message_repository=message_repository,
        lock=lock,
    )
    return GatewayRuntime(
        sessions=sessions,
        control=GatewayControl(sessions=sessions, lock=lock),
        channel_control=GatewayChannelControl(
            sessions=sessions, channel_control_store=None, lock=lock
        ),
        relay=GatewayRelay(
            sessions=sessions,
            execution=execution,
            relay_service=relay_service,
            conversation_persistence=conversation_persistence,
            message_repository=message_repository,
            lock=lock,
        ),
        execution=execution,
    )


def _insert_user(
    connection,
    *,
    user_id: str,
    username: str,
    display_name: str,  # noqa: ANN001
) -> None:
    connection.execute(
        """
        INSERT INTO users(id, username, display_name, owner_id, created_at)
        VALUES (?, ?, ?, 'owner-scope', datetime('now'))
        """,
        (user_id, username, display_name),
    )
    connection.commit()


def _seed_nonlexical_group(connection):  # noqa: ANN001, ANN202
    _insert_user(connection, user_id="owner-id", username="owner", display_name="Owner")
    _insert_user(
        connection, user_id="source-id", username="agent:S", display_name="Source"
    )
    # The legacy bulk users query iterates by the concrete users PK: Z precedes A,
    # intentionally differing from an agent-id lexical sort.
    _insert_user(
        connection, user_id="a-peer-id", username="agent:Z", display_name="Peer Z"
    )
    _insert_user(
        connection, user_id="z-peer-id", username="agent:A", display_name="Peer A"
    )
    conversation = ConversationRepository(connection).create_conversation(
        title="nonlex group",
        participant_ids=["owner-id", "source-id", "a-peer-id", "z-peer-id"],
        caller_owner_id="owner-scope",
    )
    profiles = AgentProfileRepository(connection)
    for agent_id, node_id in (
        ("S", "node-source"),
        ("Z", "node-z-old"),
        ("A", "node-a-old"),
    ):
        profiles.upsert_profile(
            agent_id=agent_id,
            owner_id="owner-scope",
            node_id=node_id,
            display_name=f"Agent {agent_id}",
            description="",
            system_prompt=f"You are {agent_id}.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=f"/work/{agent_id}",
        )
    return conversation


def test_direct_dispatch_rebinds_to_latest_node_before_enqueue(tmp_path: Path) -> None:
    """A post-write agent rebind routes relay/push to the replacement node."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    old_ws = _RecordingWebSocket()
    new_ws = _RecordingWebSocket()
    persistence = _RebindAfterDispatchPersistence(connection)
    handler = _build_runtime(
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


def test_group_route_bulk_hydrates_peers_in_legacy_query_order(
    tmp_path: Path,
) -> None:
    """Peer identity follows the old bulk query without per-participant user reads."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    conversation = _seed_nonlexical_group(connection)
    persistence = GatewayConversationPersistence(connection)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)

    route = persistence.group_reply_route(
        conversation_id=conversation.id, source_agent_id="S"
    )

    connection.set_trace_callback(None)
    assert route is not None
    assert [target.agent_id for target in route.targets] == ["Z", "A"]
    participant_bulk_queries = [
        statement for statement in statements if "FROM users WHERE id IN" in statement
    ]
    per_participant_queries = [
        statement
        for statement in statements
        if "FROM users" in statement and "WHERE id =" in statement
    ]
    assert len(participant_bulk_queries) == 1
    assert per_participant_queries == []


def test_group_fanout_rebinds_later_peer_before_its_enqueue(tmp_path: Path) -> None:
    """A peer rebound during the prior push is routed to its replacement node."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    conversation = _seed_nonlexical_group(connection)
    relay_service = RelayService(connection)
    sockets = {
        node_id: _RecordingWebSocket()
        for node_id in (
            "node-source",
            "node-z-old",
            "node-a-old",
            "node-a-new",
        )
    }
    handler = _build_runtime(
        relay_service=relay_service,
        node_persistence=GatewayNodePersistence(connection),
        conversation_persistence=GatewayConversationPersistence(connection),
        message_repository=MessageRepository(connection),
    )
    sockets["node-z-old"]._after_first_send = lambda: (
        connection.execute(
            "UPDATE agent_profiles SET node_id = 'node-a-new' WHERE agent_id = 'A'"
        ),
        connection.commit(),
    )
    for node_id, agents in (
        ("node-source", ["S"]),
        ("node-z-old", ["Z"]),
        ("node-a-old", ["A"]),
        ("node-a-new", []),
    ):
        asyncio.run(
            handler.handle_message(
                websocket=sockets[node_id],
                message_type="node.register",
                payload={"node_id": node_id, "agents": agents, "capabilities": {}},
            )
        )
    message = MessageRepository(connection).create_message(
        conversation_id=conversation.id,
        sender_user_id="owner-id",
        sender_type="user",
        content="ask source",
    )
    original = relay_service.enqueue_message_relay(
        message=message,
        target_node_id="node-source",
        idempotency_key="group-source",
        sender_user_id="owner-id",
        conversation_type="group",
        _override_agent_id="S",
    ).relay_task

    response = asyncio.run(
        handler.handle_message(
            websocket=sockets["node-source"],
            message_type="node.delivery_receipt",
            payload={
                "node_id": "node-source",
                "relay_task_id": original.relay_task_id,
                "delivery_status": "completed",
                "detail": "source reply",
            },
        )
    )

    assert response is not None and response["type"] == "ack"
    rows = connection.execute(
        """
        SELECT idempotency_key, target_node_id FROM relay_tasks
        WHERE idempotency_key LIKE 'agent-reply:%'
        ORDER BY rowid
        """
    ).fetchall()
    assert [str(row["idempotency_key"]).rsplit(":", 1)[1] for row in rows] == [
        "Z",
        "A",
    ]
    assert [str(row["target_node_id"]) for row in rows] == [
        "node-z-old",
        "node-a-new",
    ]
    assert sockets["node-a-old"].sent_json == []
    assert [frame["type"] for frame in sockets["node-a-new"].sent_json] == [
        "relay.message"
    ]
