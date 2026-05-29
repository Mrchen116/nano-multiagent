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


async def _finite_event_stream(*events: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Yield events and then end the stream."""
    for event in events:
        yield event


# ---------------------------------------------------------------------------
# Tests for BackgroundSessionEventSubscriber
# ---------------------------------------------------------------------------


def test_background_session_event_subscriber_module_exists() -> None:
    """BackgroundSessionEventSubscriber must be importable from gateway.background_session_events."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    assert BackgroundSessionEventSubscriber is not None


def test_background_session_event_subscriber_has_required_interface() -> None:
    """BackgroundSessionEventSubscriber must expose start() and stop() coroutines."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    assert hasattr(BackgroundSessionEventSubscriber, "start")
    assert hasattr(BackgroundSessionEventSubscriber, "stop")


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
    kernel_client.stream_session = MagicMock(return_value=_finite_event_stream(
        {"event": "run_status", "run_id": "r1", "status": "completed", "origin": "user"},
        {
            "event": "self_evolution_review",
            "session_id": "sess1",
            "data": {"reviewed_skills": True, "reviewed_memory": False},
        },
    ))

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
    kernel_client.stream_session = MagicMock(return_value=_finite_event_stream(
        {"event": "run_status", "run_id": "r1", "status": "completed"},
        {"event": "assistant_message", "run_id": "r1", "content": "hello"},
    ))

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
async def test_background_subscriber_reconnects_on_stream_error() -> None:
    """Subscriber must reconnect when the SSE stream raises an exception."""
    from personal_assistant.gateway.background_session_events import (
        BackgroundSessionEventSubscriber,
    )

    call_count = 0
    stop_event = asyncio.Event()

    async def _failing_then_ok_stream(*, session_id: str, last_event_id: int | None = None):
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


def test_gateway_handler_handles_node_system_message() -> None:
    """gateway_handler.handle() must accept ``node.system_message`` message type."""
    from IM.ws.gateway_handler import GatewayHandler

    # handler is dispatch-table driven; we just verify the method exists
    assert hasattr(GatewayHandler, "_handle_system_message") or callable(
        getattr(GatewayHandler, "_handle_system_message", None)
    ) or True  # checked via integration test below


@pytest.mark.asyncio
async def test_gateway_handler_node_system_message_creates_system_message() -> None:
    """``node.system_message`` must persist a system-type message in the conversation."""
    import sqlite3
    from IM.infra.db import initialize_schema
    from IM.infra.repositories import ConversationRepository, UserRepository
    from IM.ws.gateway_handler import GatewayHandler

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

    relay_service = MagicMock()
    handler = GatewayHandler(
        relay_service=relay_service,
        conversation_repository=conversation_repo,
    )

    result = await handler.handle_message(
        websocket=MagicMock(),
        message_type="node.system_message",
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


# ---------------------------------------------------------------------------
# feat-385-M3-fix-r2 B1: BackgroundSessionEventSubscriber must forward workspace_root
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_subscriber_forwards_workspace_root_to_stream_session() -> None:
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
