"""Cross-connection concurrency coverage for Gateway agent dispatch."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from IM.application.relay_service import RelayService
from IM.infra.db import connect, initialize_schema
from IM.infra.gateway_persistence import (
    AgentDispatchRecord,
    GatewayConversationPersistence,
    GatewayNodePersistence,
)
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.messages import MessageRepository
from IM.infra.repositories.users import UserRepository
from IM.ws.gateway_handler import GatewayHandler


class _PreInsertBarrierPersistence(GatewayConversationPersistence):
    """Make both handlers enter the durable first-write-wins race."""

    def __init__(self, *, db_path: Path, barrier: Barrier) -> None:
        self.connection = connect(db_path)
        super().__init__(self.connection)
        self._barrier = barrier

    def record_dispatch(self, record: AgentDispatchRecord) -> AgentDispatchRecord:
        self._barrier.wait(timeout=5)
        return super().record_dispatch(record)


def _dispatch_once(*, db_path: Path, barrier: Barrier) -> dict[str, object]:
    persistence = _PreInsertBarrierPersistence(db_path=db_path, barrier=barrier)
    handler = GatewayHandler(
        relay_service=RelayService(persistence.connection),
        conversation_persistence=persistence,
        message_repository=MessageRepository(persistence.connection),
    )
    try:
        response = asyncio.run(
            handler.handle_message(
                websocket=object(),
                message_type="agent.message",
                payload={
                    "from_session_id": "A|tool_call:shared-call",
                    "to": "agent:B",
                    "text": "concurrent hello",
                },
            )
        )
        assert response is not None
        return response
    finally:
        persistence.connection.close()


def test_competing_handlers_relay_and_ack_only_the_durable_winner(
    tmp_path: Path,
) -> None:
    """Two process-local locks cannot permit the losing message to escape."""
    db_path = tmp_path / "im.db"
    setup = connect(db_path)
    initialize_schema(setup)
    GatewayNodePersistence(setup).register(
        node_id="node-b",
        node_name="Node B",
        version="v1",
        agent_ids=["A", "B"],
        agent_workspaces={},
    )
    users = UserRepository(setup)
    source = users.get_user_by_username(username="agent:A")
    target = users.get_user_by_username(username="agent:B")
    assert source is not None and target is not None
    conversation = ConversationRepository(setup).create_conversation(
        title="A / B",
        participant_ids=[source.id, target.id],
        caller_owner_id=None,
    )
    setup.close()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: _dispatch_once(db_path=db_path, barrier=barrier), range(2)
            )
        )

    observed = connect(db_path)
    winner = GatewayConversationPersistence(observed).find_dispatch(
        dispatch_request_key="A:shared-call"
    )
    assert winner is not None
    assert all(response["type"] == "ack" for response in responses)
    assert {response["payload"]["message_id"] for response in responses} == {
        winner.message_id
    }
    assert {response["payload"]["conversation_id"] for response in responses} == {
        winner.conversation_id
    }

    messages = MessageRepository(observed).list_messages(
        conversation_id=conversation.id
    )
    assert len(messages) == 2, "the existing non-atomic message side effect is retained"
    relay_rows = observed.execute(
        "SELECT message_id FROM relay_tasks ORDER BY created_at, relay_task_id"
    ).fetchall()
    assert [str(row["message_id"]) for row in relay_rows] == [winner.message_id]
