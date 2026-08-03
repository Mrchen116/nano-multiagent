"""Public IM user-stream event names and payload serialization contracts."""

from IM.api.ws.event_types import (
    EVENT_AGENT_CHANNEL_STATUS_CHANGED,
    EVENT_AGENT_STATUS_CHANGED,
    EVENT_MESSAGE_COMPLETED,
    EVENT_MESSAGE_CREATED,
    EVENT_MESSAGE_DELTA,
    EVENT_NODE_STATUS_CHANGED,
    EVENT_THINKING_SEGMENT,
    EVENT_TOOL_CALL_COMPLETED,
    EVENT_TOOL_CALL_UPSERTED,
    build_agent_channel_status_changed_payload,
    build_agent_status_changed_payload,
    build_message_completed_payload,
    build_message_created_payload,
    build_message_delta_payload,
    build_node_status_changed_payload,
    build_thinking_segment_payload,
    build_tool_call_completed_payload,
    build_tool_call_upserted_payload,
)
from IM.domain.models import (
    Actor,
    Attachment,
    Message,
    ThinkingSegment,
    TokenUsage,
    ToolCall,
)


def test_event_type_constants_are_stable_strings() -> None:
    assert {
        EVENT_MESSAGE_CREATED,
        EVENT_MESSAGE_DELTA,
        EVENT_MESSAGE_COMPLETED,
        EVENT_THINKING_SEGMENT,
        EVENT_TOOL_CALL_UPSERTED,
        EVENT_TOOL_CALL_COMPLETED,
        EVENT_NODE_STATUS_CHANGED,
        EVENT_AGENT_STATUS_CHANGED,
        EVENT_AGENT_CHANNEL_STATUS_CHANGED,
    } == {
        "message.created",
        "message.delta",
        "message.completed",
        "thinking.segment",
        "tool_call.upserted",
        "tool_call.completed",
        "node.status_changed",
        "agent.status_changed",
        "agent.channel.status_changed",
    }


def test_message_created_payload_preserves_live_insert_fields() -> None:
    message = Message(
        id="message-1",
        conversation_id="conversation-1",
        sender=Actor(type="user", id="owner-1", display_name="Alice"),
        sender_user_id="owner-1",
        sender_type="user",
        content="from feishu",
        created_at="2026-01-01T00:00:00Z",
        attachments=[
            Attachment(
                url="https://example.test/a.png",
                content_type="image/png",
                file_name="a.png",
            )
        ],
        thinking=[ThinkingSegment(seq=0, text="inspect")],
    )

    payload = build_message_created_payload(message=message)

    assert payload["message_id"] == "message-1"
    assert payload["conversation_id"] == "conversation-1"
    assert payload["content"] == "from feishu"
    assert payload["attachments"] == [
        {
            "url": "https://example.test/a.png",
            "content_type": "image/png",
            "file_name": "a.png",
        }
    ]
    assert payload["sender_display_name"] == "Alice"
    assert payload["thinking"] == [{"seq": 0, "text": "inspect"}]


def test_incremental_message_payloads_preserve_identity_and_content() -> None:
    delta = build_message_delta_payload(
        conversation_id="conversation-1", message_id="message-1", delta_text="hello"
    )
    thinking = build_thinking_segment_payload(
        conversation_id="conversation-1",
        message_id="message-1",
        segment=ThinkingSegment(seq=1, text="reason"),
    )

    assert delta == {
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "delta_text": "hello",
    }
    assert thinking == {
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "thinking_segment": {"seq": 1, "text": "reason"},
    }


def test_tool_call_lifecycle_payloads_preserve_state() -> None:
    running = ToolCall(
        id="call-1",
        name="read_file",
        status="running",
        input={"path": "x"},
    )
    completed = ToolCall(
        id="call-1",
        name="read_file",
        status="completed",
        input={"path": "x"},
        output="ok",
        duration_ms=22,
    )

    upserted = build_tool_call_upserted_payload(
        conversation_id="conversation-1", message_id="message-1", tool_call=running
    )
    finished = build_tool_call_completed_payload(
        conversation_id="conversation-1", message_id="message-1", tool_call=completed
    )

    assert upserted["tool_call"] == {
        "id": "call-1",
        "name": "read_file",
        "status": "running",
        "input": {"path": "x"},
    }
    assert finished["tool_call"] == {
        "id": "call-1",
        "name": "read_file",
        "status": "completed",
        "input": {"path": "x"},
        "duration_ms": 22,
        "output": "ok",
    }


def test_message_completed_payload_preserves_turn_metadata() -> None:
    payload = build_message_completed_payload(
        conversation_id="conversation-1",
        message_id="message-1",
        content="done",
        token_usage=TokenUsage(
            output=42,
            context_used=1000,
            context_window=200000,
            total=1042,
            cache_read_tokens=270,
            cache_total_input_tokens=400,
        ),
        kernel_message_id="kernel-message-1",
        elapsed_ms=4200,
    )

    assert payload["content"] == "done"
    assert payload["token_usage"] == {
        "output": 42,
        "context_used": 1000,
        "context_window": 200000,
        "total": 1042,
        "cache_read_tokens": 270,
        "cache_total_input_tokens": 400,
    }
    assert payload["kernel_message_id"] == "kernel-message-1"
    assert payload["elapsed_ms"] == 4200


def test_message_completed_payload_keeps_optional_metadata_absent() -> None:
    payload = build_message_completed_payload(
        conversation_id="conversation-1",
        message_id="message-1",
        content="done",
        token_usage=None,
    )

    assert payload["token_usage"] is None
    assert payload.get("kernel_message_id") is None
    assert payload.get("elapsed_ms") is None


def test_status_payloads_preserve_scope_and_failure_details() -> None:
    online = build_node_status_changed_payload(
        seq=7,
        node_id="node-1",
        status="online",
        last_heartbeat_at="2026-05-11T10:00:00Z",
        last_error=None,
    )
    offline = build_node_status_changed_payload(
        seq=8,
        node_id="node-1",
        status="offline",
        last_heartbeat_at="2026-05-11T10:00:00Z",
        last_error="heartbeat_timeout",
    )

    assert online["status"] == "online"
    assert offline["last_error"] == "heartbeat_timeout"
    assert build_agent_status_changed_payload(
        seq=3, agent_id="agent-x", status="online"
    ) == {"seq": 3, "agent_id": "agent-x", "status": "online"}
    assert build_agent_channel_status_changed_payload(
        seq=4, agent_id="agent-x", channel_id="channel-a"
    ) == {"seq": 4, "agent_id": "agent-x", "channel_id": "channel-a"}
