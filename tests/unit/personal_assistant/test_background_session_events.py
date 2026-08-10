"""R6 tests: PA gateway background session event subscriber.

Verifies that ``self_evolution_review`` session events published by the
background hook reach the IM conversation as system messages even when
the main turn's SSE loop has already terminated.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper stubs
# ---------------------------------------------------------------------------


async def _event_stream(*events: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Yield a sequence of mock SSE events."""
    for event in events:
        yield event
    # After yielding all events, block indefinitely (simulating persistent stream).
    await asyncio.sleep(10)


async def _finite_event_stream(
    *events: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Yield events and then end the stream."""
    for event in events:
        yield event


@pytest.mark.asyncio
async def test_background_subscriber_calls_callback_on_self_evolution_review() -> None:
    """When a self_evolution_review event arrives in the SSE stream, the on_event callback is called."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    received: list[dict[str, Any]] = []

    async def _on_event(event: Mapping[str, Any]) -> None:
        received.append(dict(event))

    kernel_client = MagicMock()
    kernel_client.stream_session = MagicMock(
        return_value=_finite_event_stream(
            {
                "event": "run_status",
                "run_id": "r1",
                "status": "completed",
                "origin": "user",
            },
            {
                "event": "self_evolution_review",
                "session_id": "sess1",
                "data": {"reviewed_skills": True, "reviewed_memory": False},
            },
        )
    )

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess1",
        on_event=_on_event,
        after_sequence=0,
    )
    await subscriber.start()
    # Give background task time to process
    await asyncio.sleep(0.05)
    await subscriber.stop()

    assert len(received) == 1
    assert received[0]["event"] == "self_evolution_review"
    assert received[0]["data"]["reviewed_skills"] is True


@pytest.mark.asyncio
async def test_background_subscriber_ignores_non_session_events() -> None:
    """The subscriber must not invoke callback for regular run_status or assistant_message events."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    received: list[dict[str, Any]] = []

    async def _on_event(event: Mapping[str, Any]) -> None:
        received.append(dict(event))

    kernel_client = MagicMock()
    kernel_client.stream_session = MagicMock(
        return_value=_finite_event_stream(
            {"event": "run_status", "run_id": "r1", "status": "completed"},
            {"event": "assistant_message", "run_id": "r1", "content": "hello"},
        )
    )

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess1",
        on_event=_on_event,
        after_sequence=0,
    )
    await subscriber.start()
    await asyncio.sleep(0.05)
    await subscriber.stop()

    assert received == []


@pytest.mark.asyncio
async def test_background_subscriber_routes_only_marked_self_evolution_skill() -> None:
    """Only source-marked skill creation is a persistent business event."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    skill_events: list[dict[str, Any]] = []

    async def _on_skill_created(event: Mapping[str, Any]) -> None:
        skill_events.append(dict(event))

    kernel_client = MagicMock()
    kernel_client.stream_session = MagicMock(
        return_value=_finite_event_stream(
            {
                "event": "skill_created",
                "name": "ordinary-skill",
                "scope": "agent",
                "sequence_num": 8,
            },
            {
                "event": "skill_created",
                "name": "review-skill",
                "scope": "agent",
                "source": "self_evolution",
                "sequence_num": 9,
            },
        )
    )
    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess1",
        on_event=AsyncMock(),
        skill_created_callback=_on_skill_created,
        reconnect_delay=10,
    )

    await subscriber.start()
    await asyncio.sleep(0.05)
    await subscriber.stop()

    assert [event["name"] for event in skill_events] == ["review-skill"]


@pytest.mark.asyncio
async def test_background_subscriber_reconnects_after_marked_skill_cursor() -> None:
    """Reconnect resumes after the handled skill sequence instead of replaying it."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    stream_anchors: list[int | None] = []
    received: list[str] = []
    complete = asyncio.Event()

    async def _stream(
        *,
        session_id: str,
        last_event_id: int | None = None,
        **_kwargs: object,
    ) -> AsyncIterator[dict[str, Any]]:
        del session_id
        stream_anchors.append(last_event_id)
        if last_event_id is None:
            yield {
                "event": "skill_created",
                "name": "first",
                "source": "self_evolution",
                "sequence_num": 8,
            }
            raise RuntimeError("disconnect after first event")
        assert last_event_id == 8
        yield {
            "event": "skill_created",
            "name": "second",
            "source": "self_evolution",
            "sequence_num": 9,
        }
        await complete.wait()

    async def _on_skill_created(event: Mapping[str, Any]) -> None:
        received.append(str(event["name"]))
        if len(received) == 2:
            complete.set()

    kernel_client = MagicMock()
    kernel_client.stream_session = _stream
    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess1",
        on_event=AsyncMock(),
        skill_created_callback=_on_skill_created,
        reconnect_delay=0.01,
    )

    await subscriber.start()
    await asyncio.wait_for(complete.wait(), timeout=1)
    await subscriber.stop()

    assert received == ["first", "second"]
    assert stream_anchors[:2] == [None, 8]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("callback_kind", "event"),
    [
        (
            "background",
            {
                "event": "assistant_message",
                "origin": "background_task",
                "content": "ordinary result",
            },
        ),
        (
            "skill",
            {
                "event": "skill_created",
                "source": "self_evolution",
                "name": "created-skill",
            },
        ),
        ("notice", {"event": "self_evolution_review"}),
    ],
)
async def test_close_waits_for_each_accepted_callback(
    callback_kind: str,
    event: dict[str, Any],
) -> None:
    """All three routed callback classes share the same shutdown handoff."""

    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    callback_started = asyncio.Event()
    release_callback = asyncio.Event()

    async def _callback(_event: Mapping[str, Any]) -> None:
        callback_started.set()
        await release_callback.wait()

    async def _noop(_event: Mapping[str, Any]) -> None:
        return None

    kernel_client = MagicMock()
    kernel_client.stream_session = MagicMock(return_value=_event_stream(event))
    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id=f"sess-{callback_kind}",
        on_event=_callback if callback_kind == "notice" else _noop,
        bg_run_output_callback=(_callback if callback_kind == "background" else None),
        skill_created_callback=_callback if callback_kind == "skill" else None,
    )

    await subscriber.start()
    await asyncio.wait_for(callback_started.wait(), timeout=1)
    close_task = asyncio.create_task(
        subscriber.aclose(asyncio.get_running_loop().time() + 1)
    )
    await asyncio.sleep(0)

    assert not close_task.done()
    release_callback.set()
    await close_task


@pytest.mark.asyncio
async def test_background_subscriber_reconnects_on_stream_error() -> None:
    """Subscriber must reconnect when the SSE stream raises an exception."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    call_count = 0
    stop_event = asyncio.Event()

    async def _failing_then_ok_stream(
        *,
        session_id: str,
        last_event_id: int | None = None,
        workspace_root: str | None = None,
        **_kwargs,
    ):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated connection error")
        # Second call: yield one session event then block until stopped
        yield {
            "event": "self_evolution_review",
            "session_id": session_id,
            "data": {"reviewed_skills": False, "reviewed_memory": True},
        }
        await stop_event.wait()

    received: list[dict[str, Any]] = []

    async def _on_event(event: Mapping[str, Any]) -> None:
        received.append(dict(event))
        stop_event.set()

    kernel_client = MagicMock()
    kernel_client.stream_session = _failing_then_ok_stream

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess1",
        on_event=_on_event,
        after_sequence=0,
        reconnect_delay=0.01,
    )
    await subscriber.start()
    # Wait for reconnect + event processing (with generous timeout)
    for _ in range(40):
        if received:
            break
        await asyncio.sleep(0.01)
    await subscriber.stop()

    assert len(received) >= 1
    assert received[0]["data"]["reviewed_memory"] is True


# ---------------------------------------------------------------------------
# Tests for IM gateway_handler node.system_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateway_handler_node_system_message_creates_system_message() -> None:
    """``node.system_message`` must persist a system-type message in the conversation."""
    import sqlite3
    from IM.infra.db import initialize_schema
    from IM.infra.gateway_persistence import GatewayConversationPersistence
    from IM.infra.repositories.conversations import ConversationRepository
    from IM.infra.repositories.messages import MessageRepository
    from IM.infra.repositories.users import UserRepository
    from IM.ws.gateway.execution import GatewayExecution
    from IM.ws.gateway.relay import GatewayRelay
    from IM.ws.gateway.sessions import GatewaySessions

    # Use the real IM schema so all column names are correct.
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)

    # Create a test user (conversation owner) and a direct conversation.
    user_repo = UserRepository(conn)
    owner = user_repo.create_user(username="test_owner", display_name="Test Owner")

    conversation_repo = ConversationRepository(connection=conn)
    conv = conversation_repo.create_conversation(
        title="Test Chat",
        participant_ids=[owner.id],
        caller_owner_id=owner.owner_id,
    )

    lock = asyncio.Lock()
    sessions = GatewaySessions(lock=lock)
    handler = GatewayRelay(
        sessions=sessions,
        execution=GatewayExecution(sessions=sessions, lock=lock),
        relay_service=MagicMock(),
        conversation_persistence=GatewayConversationPersistence(conn),
        message_repository=MessageRepository(conn),
        lock=lock,
    )

    result = await handler.handle_system_message(
        payload={
            "conversation_id": conv.id,
            "text": "· background self-evolution review: skills updated",
        },
    )

    assert result is not None
    assert result.get("type") != "error", f"unexpected error: {result}"
    assert result.get("type") == "ack"
    assert "message_id" in result.get("payload", {})

    # Verify the message was persisted with sender_type=system
    row = conn.execute(
        "SELECT sender_type, content FROM messages WHERE conversation_id = ?",
        (conv.id,),
    ).fetchone()
    assert row is not None
    assert row["sender_type"] == "system"
    assert "self-evolution review" in row["content"]


@pytest.mark.asyncio
async def test_gateway_handler_structured_system_message_is_attributed_and_idempotent() -> (
    None
):
    """A trusted structured notice publishes once with the profile-name snapshot."""
    import json
    import sqlite3

    from IM.infra.db import initialize_schema
    from IM.infra.gateway_persistence import GatewayConversationPersistence
    from IM.infra.repositories.agents import AgentProfileRepository
    from IM.infra.repositories.conversations import ConversationRepository
    from IM.infra.repositories.messages import MessageRepository
    from IM.infra.repositories.users import UserRepository
    from IM.ws.gateway.execution import GatewayExecution
    from IM.ws.gateway.relay import GatewayRelay
    from IM.ws.gateway.sessions import GatewaySessions

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)
    users = UserRepository(conn)
    owner = users.create_user(username="owner", display_name="Owner")
    source = users.create_user(username="agent:product", display_name="Old Product")
    conversation = ConversationRepository(conn).create_conversation(
        title="group",
        participant_ids=[owner.id, source.id],
        caller_owner_id=owner.owner_id,
    )
    AgentProfileRepository(conn).upsert_profile(
        agent_id="product",
        owner_id=owner.owner_id,
        node_id="node-1",
        display_name="SpecLab Product",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/work/product",
    )
    lock = asyncio.Lock()
    sessions = GatewaySessions(lock=lock)
    handler = GatewayRelay(
        sessions=sessions,
        execution=GatewayExecution(sessions=sessions, lock=lock),
        relay_service=MagicMock(),
        conversation_persistence=GatewayConversationPersistence(conn),
        message_repository=MessageRepository(conn),
        lock=lock,
    )
    payload = {
        "node_id": "node-1",
        "conversation_id": conversation.id,
        "idempotency_key": "self-evolution-review:sess-1:87",
        "text": "· background self-evolution review: memory updated",
        "system_notice": {
            "kind": "self_evolution_review",
            "source_agent_id": "product",
            "updated_targets": ["memory", "memory"],
        },
    }

    first = await handler.handle_system_message(payload=dict(payload))
    retried = await handler.handle_system_message(payload=dict(payload))

    assert first == retried
    rows = conn.execute(
        "SELECT id, system_notice_json FROM messages WHERE conversation_id = ?",
        (conversation.id,),
    ).fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0]["system_notice_json"]) == {
        "kind": "self_evolution_review",
        "source_agent_id": "product",
        "source_agent_display_name": "SpecLab Product",
        "updated_targets": ["memory"],
    }
    created_count = conn.execute(
        "SELECT COUNT(*) FROM conversation_events "
        "WHERE conversation_id = ? AND event_type = 'message.created'",
        (conversation.id,),
    ).fetchone()[0]
    assert created_count == 1

    rejected = await handler.handle_system_message(
        payload={**payload, "node_id": "node-other", "idempotency_key": "other"}
    )
    assert rejected["type"] == "error"
    assert rejected["payload"]["code"] == "invalid_system_message"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "missing_profile",
        "wrong_node",
        "blank_display_name",
        "missing_synthetic_user",
        "missing_conversation",
        "nonparticipant",
    ],
)
async def test_gateway_handler_rejects_untrusted_notice_without_side_effects(
    case: str,
) -> None:
    """Trust failures return one stable error and create no history/live event."""
    import sqlite3

    from IM.infra.db import initialize_schema
    from IM.infra.gateway_persistence import GatewayConversationPersistence
    from IM.infra.repositories.agents import AgentProfileRepository
    from IM.infra.repositories.conversations import ConversationRepository
    from IM.infra.repositories.messages import MessageRepository
    from IM.infra.repositories.users import UserRepository
    from IM.ws.gateway.execution import GatewayExecution
    from IM.ws.gateway.relay import GatewayRelay
    from IM.ws.gateway.sessions import GatewaySessions

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)
    users = UserRepository(conn)
    owner = users.create_user(username="owner", display_name="Owner")
    source = (
        None
        if case == "missing_synthetic_user"
        else users.create_user(username="agent:product", display_name="Product")
    )
    conversation = ConversationRepository(conn).create_conversation(
        title="group",
        participant_ids=[
            owner.id,
            *([source.id] if source is not None and case != "nonparticipant" else []),
        ],
        caller_owner_id=owner.owner_id,
    )
    if case != "missing_profile":
        AgentProfileRepository(conn).upsert_profile(
            agent_id="product",
            owner_id=owner.owner_id,
            node_id="node-1",
            display_name="" if case == "blank_display_name" else "Product",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root="/work/product",
        )
    emitted: list[object] = []
    lock = asyncio.Lock()
    sessions = GatewaySessions(lock=lock)
    handler = GatewayRelay(
        sessions=sessions,
        execution=GatewayExecution(sessions=sessions, lock=lock),
        relay_service=MagicMock(),
        conversation_persistence=GatewayConversationPersistence(conn),
        message_repository=MessageRepository(conn, notify=emitted.append),
        lock=lock,
    )

    result = await handler.handle_system_message(
        payload={
            "node_id": "node-other" if case == "wrong_node" else "node-1",
            "conversation_id": (
                "missing" if case == "missing_conversation" else conversation.id
            ),
            "idempotency_key": f"notice-{case}",
            "text": "fallback",
            "system_notice": {
                "kind": "self_evolution_review",
                "source_agent_id": "product",
                "updated_targets": ["memory"],
            },
        }
    )

    assert result["type"] == "error"
    assert result["payload"]["code"] == "invalid_system_message"
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM conversation_events "
            "WHERE event_type = 'message.created'"
        ).fetchone()[0]
        == 0
    )
    assert emitted == []


# ---------------------------------------------------------------------------
# feat-385-M3-fix-r2 B1: BackgroundSessionEventSubscriber must forward workspace_root
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_subscriber_forwards_workspace_root_to_stream_session() -> (
    None
):
    """BackgroundSessionEventSubscriber must pass workspace_root to stream_session.

    Refs #64: without workspace_root the kernel cannot locate the session JSONL and
    returns session_not_found 404.  The subscriber must accept workspace_root at
    construction time and forward it on every stream_session call.
    """
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    stream_calls: list[dict[str, object]] = []

    async def _fake_stream(**kwargs: object) -> AsyncIterator:  # type: ignore[misc]
        stream_calls.append(dict(kwargs))
        return
        yield  # Make this an async generator

    kernel_client = MagicMock()
    kernel_client.stream_session = _fake_stream

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess-b1",
        on_event=AsyncMock(),
        after_sequence=0,
        workspace_root="/tmp/agent-b1",
    )
    await subscriber.start()
    await asyncio.sleep(0.05)
    await subscriber.stop()

    assert stream_calls, "stream_session must have been called at least once"
    assert stream_calls[0].get("workspace_root") == "/tmp/agent-b1", (
        "BackgroundSessionEventSubscriber must forward workspace_root to stream_session "
        f"(Refs #64); got call kwargs: {stream_calls[0]}"
    )


# ---------------------------------------------------------------------------
# bugfix-404-M3: BACKGROUND_TASK run output relay via bg_run_output_callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bg_subscriber_routes_background_task_assistant_message_to_callback() -> (
    None
):
    """BACKGROUND_TASK origin assistant_message must be routed to bg_run_output_callback.

    When a BACKGROUND_TASK-origin run finishes and produces an assistant_message event,
    the subscriber must call bg_run_output_callback with the event — not the standard
    on_event path (which is reserved for session-level events like self_evolution_review).
    """
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    routed: list[dict[str, Any]] = []
    on_event_received: list[dict[str, Any]] = []

    async def _bg_run_output_callback(event: Mapping[str, Any]) -> None:
        routed.append(dict(event))

    async def _on_event(event: Mapping[str, Any]) -> None:
        on_event_received.append(dict(event))

    kernel_client = MagicMock()
    kernel_client.stream_session = MagicMock(
        return_value=_finite_event_stream(
            {
                "event": "assistant_message",
                "run_id": "bg-run-1",
                "content": "BG404DONE output",
                "origin": "background_task",
            },
            {
                "event": "run_status",
                "run_id": "bg-run-1",
                "status": "completed",
                "origin": "background_task",
            },
        )
    )

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess-bg",
        on_event=_on_event,
        after_sequence=0,
        bg_run_output_callback=_bg_run_output_callback,
    )
    await subscriber.start()
    await asyncio.sleep(0.05)
    await subscriber.stop()

    # bg_run_output_callback must receive the BACKGROUND_TASK assistant_message
    assert len(routed) == 1, f"expected 1 routed event, got {routed}"
    assert routed[0]["event"] == "assistant_message"
    assert routed[0]["content"] == "BG404DONE output"
    assert routed[0]["origin"] == "background_task"

    # on_event must NOT be called for BACKGROUND_TASK assistant_message events
    assert on_event_received == [], (
        f"on_event should not be called for BACKGROUND_TASK assistant_message; got {on_event_received}"
    )


@pytest.mark.asyncio
async def test_bg_subscriber_ignores_non_background_task_assistant_message() -> None:
    """Non-BACKGROUND_TASK assistant_message events must NOT be routed to bg_run_output_callback.

    The bg_run_output_callback is exclusively for BACKGROUND_TASK-origin run outputs.
    Regular user-origin or missing-origin assistant_message events must not trigger it.
    """
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    routed: list[dict[str, Any]] = []

    async def _bg_run_output_callback(event: Mapping[str, Any]) -> None:
        routed.append(dict(event))

    kernel_client = MagicMock()
    kernel_client.stream_session = MagicMock(
        return_value=_finite_event_stream(
            # user-origin assistant_message (normal turn reply)
            {
                "event": "assistant_message",
                "run_id": "user-run-1",
                "content": "normal reply",
                "origin": "user",
            },
            # missing origin assistant_message
            {
                "event": "assistant_message",
                "run_id": "user-run-2",
                "content": "another reply",
            },
        )
    )

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=kernel_client,
        session_id="sess-user",
        on_event=AsyncMock(),
        after_sequence=0,
        bg_run_output_callback=_bg_run_output_callback,
    )
    await subscriber.start()
    await asyncio.sleep(0.05)
    await subscriber.stop()

    # bg_run_output_callback must NOT be called for non-BACKGROUND_TASK events
    assert routed == [], (
        f"bg_run_output_callback should not be called for non-BACKGROUND_TASK events; got {routed}"
    )
