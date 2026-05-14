"""Tests for IM WS event type constants and payload builders (feat-340-M2 R2)."""

from pathlib import Path

from IM.api.ws.event_types import (
    EVENT_AGENT_STATUS_CHANGED,
    EVENT_MESSAGE_COMPLETED,
    EVENT_MESSAGE_CREATED,
    EVENT_MESSAGE_DELTA,
    EVENT_NODE_STATUS_CHANGED,
    EVENT_TOOL_CALL_COMPLETED,
    EVENT_TOOL_CALL_UPSERTED,
    build_agent_status_changed_payload,
    build_message_completed_payload,
    build_message_created_payload,
    build_message_delta_payload,
    build_node_status_changed_payload,
    build_tool_call_completed_payload,
    build_tool_call_upserted_payload,
)
from IM.domain.models import Message, TokenUsage, ToolCall
from IM.infra.db import connect, initialize_schema
from IM.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)


def test_event_type_constants_are_stable_strings() -> None:
    assert EVENT_MESSAGE_CREATED == "message.created"
    assert EVENT_MESSAGE_DELTA == "message.delta"
    assert EVENT_MESSAGE_COMPLETED == "message.completed"
    assert EVENT_TOOL_CALL_UPSERTED == "tool_call.upserted"
    assert EVENT_TOOL_CALL_COMPLETED == "tool_call.completed"
    assert EVENT_NODE_STATUS_CHANGED == "node.status_changed"
    assert EVENT_AGENT_STATUS_CHANGED == "agent.status_changed"


def _make_agent_message(tmp_path: Path) -> Message:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    alice = users.create_user(username="alice", display_name="Alice")
    conv = conversations.create_conversation(title="t", participant_ids=[alice.id])
    return messages.create_message(
        conversation_id=conv.id,
        sender_user_id=alice.id,
        content="hi",
    )


def test_build_message_created_payload(tmp_path: Path) -> None:
    msg = _make_agent_message(tmp_path)
    payload = build_message_created_payload(message=msg)
    assert payload["conversation_id"] == msg.conversation_id
    assert payload["message_id"] == msg.id
    assert payload["sender_user_id"] == msg.sender_user_id
    assert payload["sender_type"] == msg.sender_type
    assert payload["content"] == "hi"
    # Optional fields not yet populated, encode as None or absent.
    assert payload.get("tool_calls") in (None, [])
    assert payload.get("token_usage") is None


def test_build_message_delta_payload() -> None:
    payload = build_message_delta_payload(
        conversation_id="c1", message_id="m1", delta_text="hello "
    )
    assert payload == {
        "conversation_id": "c1",
        "message_id": "m1",
        "delta_text": "hello ",
    }


def test_build_tool_call_upserted_payload() -> None:
    tc = ToolCall(
        id="tc1",
        name="read_file",
        status="running",
        duration_ms=None,
        input={"p": "x"},
        output=None,
    )
    payload = build_tool_call_upserted_payload(
        conversation_id="c1", message_id="m1", tool_call=tc
    )
    assert payload["conversation_id"] == "c1"
    assert payload["message_id"] == "m1"
    assert payload["tool_call"]["id"] == "tc1"
    assert payload["tool_call"]["name"] == "read_file"
    assert payload["tool_call"]["status"] == "running"
    assert payload["tool_call"]["input"] == {"p": "x"}
    assert "duration_ms" not in payload["tool_call"]
    assert "output" not in payload["tool_call"]


def test_build_tool_call_completed_payload() -> None:
    tc = ToolCall(
        id="tc1", name="read_file", status="completed", duration_ms=22, input={}, output="ok"
    )
    payload = build_tool_call_completed_payload(
        conversation_id="c1", message_id="m1", tool_call=tc
    )
    assert payload["tool_call"]["status"] == "completed"
    assert payload["tool_call"]["duration_ms"] == 22
    assert payload["tool_call"]["output"] == "ok"


def test_build_message_completed_payload_with_token_usage() -> None:
    usage = TokenUsage(output=42, context_used=1000, context_window=200000)
    payload = build_message_completed_payload(
        conversation_id="c1", message_id="m1", content="full text", token_usage=usage
    )
    assert payload["content"] == "full text"
    assert payload["token_usage"] == {
        "output": 42,
        "context_used": 1000,
        "context_window": 200000,
    }


def test_build_message_completed_payload_without_token_usage() -> None:
    payload = build_message_completed_payload(
        conversation_id="c1", message_id="m1", content="x", token_usage=None
    )
    assert payload["token_usage"] is None


def test_build_node_status_changed_payload_online() -> None:
    payload = build_node_status_changed_payload(
        seq=7,
        node_id="node-1",
        status="online",
        last_heartbeat_at="2026-05-11T10:00:00Z",
        last_error=None,
    )
    assert payload == {
        "seq": 7,
        "node_id": "node-1",
        "status": "online",
        "last_heartbeat_at": "2026-05-11T10:00:00Z",
        "last_error": None,
    }


def test_build_node_status_changed_payload_offline_with_error() -> None:
    payload = build_node_status_changed_payload(
        seq=8,
        node_id="node-1",
        status="offline",
        last_heartbeat_at="2026-05-11T10:00:00Z",
        last_error="heartbeat_timeout",
    )
    assert payload["status"] == "offline"
    assert payload["last_error"] == "heartbeat_timeout"


def test_build_agent_status_changed_payload() -> None:
    payload = build_agent_status_changed_payload(seq=3, agent_id="agent-x", status="online")
    assert payload == {"seq": 3, "agent_id": "agent-x", "status": "online"}
