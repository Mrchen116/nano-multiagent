"""End-to-end test: kernel SSE-shaped events → EventBridge → IM DB + WS broadcast (feat-340-M2 R4).

This is the M2 exit-criteria integration test: model a realistic kernel run's event sequence
(message_update deltas + tool_call upsert/complete + token_usage on completion) and prove
that running it through the bridge results in the right ``messages`` row and the right
``conversation_events`` rows ready for WS broadcast.

We do not stand up the full ``InboundPipeline`` here because the pipeline's job in production
is to forward kernel events to a registered observer (M3 will wire that observer to a bridge
client). M2 owns the bridge contract; pipeline wiring uses the seam added in this milestone.
"""

import json
from pathlib import Path

from IM.api.ws.event_types import (
    EVENT_MESSAGE_COMPLETED,
    EVENT_MESSAGE_CREATED,
    EVENT_MESSAGE_DELTA,
    EVENT_TOOL_CALL_COMPLETED,
    EVENT_TOOL_CALL_UPSERTED,
)
from IM.application.event_bridge import EventBridge
from IM.domain.models import ConversationEvent, TokenUsage, ToolCall
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import (
    ConversationRepository,
    EventRepository,
    MessageRepository,
    UserRepository,
)


def _translate_kernel_event(
    bridge: EventBridge, *, message_id: str, event: dict
) -> None:
    """Minimal translation map exercised by the integration test.

    Kernel SSE → bridge call. In production this lives in the gateway's event observer
    callback that the personal_assistant bootstrap registers; for the M2 integration test
    we keep it inline so we can step through a known sequence.
    """
    name = event.get("event")
    if name == "message_update":
        delta = event.get("delta_text") or ""
        if delta:
            bridge.on_message_delta(message_id=message_id, delta_text=delta)
        return
    if name == "tool_start":
        bridge.on_tool_call_upserted(
            message_id=message_id,
            tool_call=ToolCall(
                id=str(event["tool_call_id"]),
                name=str(event["tool_name"]),
                status="running",
                duration_ms=None,
                input=dict(event.get("input") or {}),
                output=None,
            ),
        )
        return
    if name == "tool_end":
        bridge.on_tool_call_completed(
            message_id=message_id,
            tool_call=ToolCall(
                id=str(event["tool_call_id"]),
                name=str(event["tool_name"]),
                status=str(event.get("status") or "completed"),
                duration_ms=int(event["duration_ms"])
                if "duration_ms" in event
                else None,
                input=dict(event.get("input") or {}),
                output=str(event.get("output"))
                if event.get("output") is not None
                else None,
            ),
        )
        return
    if name == "run_status" and event.get("status") == "completed":
        usage_payload = event.get("usage") or {}
        usage = TokenUsage(
            output=int(usage_payload.get("output", 0)),
            context_used=int(usage_payload.get("context_used", 0)),
            context_window=int(usage_payload.get("context_window", 0)),
        )
        bridge.on_message_completed(
            message_id=message_id,
            final_content=event.get("final_content"),
            token_usage=usage,
        )


def test_full_kernel_stream_persists_and_broadcasts(tmp_path: Path) -> None:
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    users = UserRepository(connection)
    conversations = ConversationRepository(connection)
    messages = MessageRepository(connection)
    events_repo = EventRepository(connection)

    alice = users.create_user(username="alice", display_name="Alice")
    agent_user = users.create_user(username="agent:planner", display_name="Planner")
    connection.execute(
        "UPDATE users SET owner_id = ? WHERE id = ?", (alice.owner_id, agent_user.id)
    )
    connection.commit()
    conv = conversations.create_conversation(title="t", participant_ids=[alice.id])

    captured: list[ConversationEvent] = []
    bridge = EventBridge(
        message_repository=messages,
        event_repository=events_repo,
        notify=captured.append,
    )

    # 1. Agent turn starts — placeholder message created.
    placeholder = bridge.on_turn_start(
        conversation_id=conv.id,
        agent_user_id=agent_user.id,
        agent_id="planner",
    )

    # 2. Simulate the kernel SSE stream — incremental text, tool call lifecycle, completion.
    kernel_events = [
        {"event": "message_update", "delta_text": "Let me check"},
        {"event": "message_update", "delta_text": " the file."},
        {
            "event": "tool_start",
            "tool_call_id": "tc1",
            "tool_name": "read_file",
            "input": {"p": "x"},
        },
        {"event": "message_update", "delta_text": " Reading..."},
        {
            "event": "tool_end",
            "tool_call_id": "tc1",
            "tool_name": "read_file",
            "status": "completed",
            "duration_ms": 22,
            "output": "OK",
            "input": {"p": "x"},
        },
        {"event": "message_update", "delta_text": " Done."},
        {
            "event": "run_status",
            "status": "completed",
            "final_content": "Let me check the file. Reading... Done.",
            "usage": {"output": 312, "context_used": 14800, "context_window": 200000},
        },
    ]
    for evt in kernel_events:
        _translate_kernel_event(bridge, message_id=placeholder.id, event=evt)

    # 3. DB has the fully-reconstructed agent message.
    final = messages.list_messages(conversation_id=conv.id)[-1]
    assert final.id == placeholder.id
    assert final.content == "Let me check the file. Reading... Done."
    assert final.delivery_status == "completed"
    assert final.tool_calls is not None and len(final.tool_calls) == 1
    only = final.tool_calls[0]
    assert only.id == "tc1"
    assert only.status == "completed"
    assert only.duration_ms == 22
    assert only.output == "OK"
    assert final.token_usage == TokenUsage(
        output=312, context_used=14800, context_window=200000
    )

    # 4. WS broadcast events emitted in lifecycle order, ready for the browser to consume.
    event_types_in_order = [e.event_type for e in captured]
    assert event_types_in_order[0] == EVENT_MESSAGE_CREATED
    assert event_types_in_order[-1] == EVENT_MESSAGE_COMPLETED
    assert EVENT_TOOL_CALL_UPSERTED in event_types_in_order
    assert EVENT_TOOL_CALL_COMPLETED in event_types_in_order
    assert event_types_in_order.count(EVENT_MESSAGE_DELTA) == 4

    # 5. Token usage rides on the completion event payload (frontend Token Chip path).
    completed = next(e for e in captured if e.event_type == EVENT_MESSAGE_COMPLETED)
    completed_payload = json.loads(completed.payload_json)
    assert completed_payload["token_usage"]["output"] == 312
    assert completed_payload["content"] == "Let me check the file. Reading... Done."

    # 6. /sync replay backed by conversation_events sees the right rows for this conversation.
    # MessageRepository.create_message emits its own ``message.sent`` event when the placeholder
    # row is inserted; the bridge then layers M2's event types on top. The browser ignores
    # ``message.sent`` and relies on ``message.created`` for the new-bubble signal, so we
    # assert only the M2 events here in lifecycle order.
    rows = connection.execute(
        "SELECT event_type FROM conversation_events WHERE conversation_id = ? ORDER BY event_id",
        (conv.id,),
    ).fetchall()
    persisted_types = [r["event_type"] for r in rows]
    m2_event_types = {
        EVENT_MESSAGE_CREATED,
        EVENT_MESSAGE_DELTA,
        EVENT_MESSAGE_COMPLETED,
        EVENT_TOOL_CALL_UPSERTED,
        EVENT_TOOL_CALL_COMPLETED,
    }
    m2_persisted = [t for t in persisted_types if t in m2_event_types]
    assert m2_persisted[0] == EVENT_MESSAGE_CREATED
    assert m2_persisted[-1] == EVENT_MESSAGE_COMPLETED
