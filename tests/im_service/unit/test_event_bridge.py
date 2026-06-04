"""Unit tests for IM.application.event_bridge.EventBridge (feat-340-M2 R3)."""

import json
from pathlib import Path

from IM.application.event_bridge import EventBridge
from IM.domain.models import Actor, ConversationEvent, TokenUsage, ToolCall
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    EventRepository,
    MessageRepository,
    UserRepository,
)


def _make_bridge(tmp_path: Path):
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)

    captured: list[ConversationEvent] = []

    def notify(event: ConversationEvent) -> None:
        captured.append(event)

    messages = MessageRepository(connection)
    events = EventRepository(connection)
    bridge = EventBridge(
        message_repository=messages,
        event_repository=events,
        notify=notify,
    )
    alice = users.create_user(username="alice", display_name="Alice")
    # Register a synthetic agent user under alice's owner scope so the bridge can address it as sender.
    agent_user = users.create_user(username="agent:planner", display_name="Planner")
    connection.execute(
        "UPDATE users SET owner_id = ? WHERE id = ?", (alice.owner_id, agent_user.id)
    )
    connection.commit()
    conv = conversations.create_conversation(title="t", participant_ids=[alice.id])
    return bridge, conv.id, agent_user.id, messages, captured


def test_on_turn_start_creates_empty_agent_message_and_emits_event(
    tmp_path: Path,
) -> None:
    bridge, conv_id, agent_uid, messages, captured = _make_bridge(tmp_path)
    msg = bridge.on_turn_start(
        conversation_id=conv_id,
        agent_user_id=agent_uid,
        agent_id="planner",
    )
    assert msg.content == ""
    assert msg.sender_type == "agent"
    assert msg.delivery_status == "running"

    # WS event emitted with right event_type and payload keys.
    assert any(e.event_type == "message.created" for e in captured)
    created_event = next(e for e in captured if e.event_type == "message.created")
    payload = json.loads(created_event.payload_json)
    assert payload["message_id"] == msg.id
    assert payload["conversation_id"] == conv_id


def test_on_message_delta_appends_content_and_emits_delta(tmp_path: Path) -> None:
    bridge, conv_id, agent_uid, messages, captured = _make_bridge(tmp_path)
    msg = bridge.on_turn_start(
        conversation_id=conv_id, agent_user_id=agent_uid, agent_id="planner"
    )
    captured.clear()

    bridge.on_message_delta(message_id=msg.id, delta_text="Hello, ")
    bridge.on_message_delta(message_id=msg.id, delta_text="world!")

    # DB content accumulated.
    reloaded = messages.list_messages(conversation_id=conv_id)
    assert reloaded[-1].content == "Hello, world!"

    deltas = [e for e in captured if e.event_type == "message.delta"]
    assert len(deltas) == 2
    p0 = json.loads(deltas[0].payload_json)
    assert p0["delta_text"] == "Hello, "
    assert p0["message_id"] == msg.id


def test_on_tool_call_lifecycle_persists_and_emits(tmp_path: Path) -> None:
    bridge, conv_id, agent_uid, messages, captured = _make_bridge(tmp_path)
    msg = bridge.on_turn_start(
        conversation_id=conv_id, agent_user_id=agent_uid, agent_id="planner"
    )
    captured.clear()

    running = ToolCall(
        id="tc1",
        name="read_file",
        status="running",
        duration_ms=None,
        input={"p": "x"},
        output=None,
    )
    bridge.on_tool_call_upserted(message_id=msg.id, tool_call=running)
    completed = ToolCall(
        id="tc1",
        name="read_file",
        status="completed",
        duration_ms=22,
        input={"p": "x"},
        output="ok",
    )
    bridge.on_tool_call_completed(message_id=msg.id, tool_call=completed)

    # DB has updated tool call.
    reloaded = messages.list_messages(conversation_id=conv_id)
    final = reloaded[-1]
    assert final.tool_calls is not None
    assert len(final.tool_calls) == 1
    assert final.tool_calls[0].status == "completed"
    assert final.tool_calls[0].output == "ok"

    # Two events emitted in order.
    tc_events = [e for e in captured if e.event_type.startswith("tool_call.")]
    assert [e.event_type for e in tc_events] == [
        "tool_call.upserted",
        "tool_call.completed",
    ]
    p1 = json.loads(tc_events[1].payload_json)
    assert p1["tool_call"]["status"] == "completed"
    assert p1["tool_call"]["duration_ms"] == 22


def test_on_message_completed_sets_token_usage_and_status(tmp_path: Path) -> None:
    bridge, conv_id, agent_uid, messages, captured = _make_bridge(tmp_path)
    msg = bridge.on_turn_start(
        conversation_id=conv_id, agent_user_id=agent_uid, agent_id="planner"
    )
    bridge.on_message_delta(message_id=msg.id, delta_text="final text")
    captured.clear()

    usage = TokenUsage(output=42, context_used=1000, context_window=200000)
    bridge.on_message_completed(
        message_id=msg.id,
        final_content="final text",
        token_usage=usage,
    )

    reloaded = messages.list_messages(conversation_id=conv_id)
    final = reloaded[-1]
    assert final.delivery_status == "completed"
    assert final.token_usage == usage
    assert final.content == "final text"

    completed_events = [e for e in captured if e.event_type == "message.completed"]
    assert len(completed_events) == 1
    payload = json.loads(completed_events[0].payload_json)
    assert payload["content"] == "final text"
    assert payload["token_usage"]["output"] == 42
