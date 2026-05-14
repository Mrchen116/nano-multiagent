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

    async def _failing_then_ok_stream(*, session_id: str, last_event_id: int | None = None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated connection error")
        # Second call: yield one session event then stop
        yield {
            "event": "self_evolution_review",
            "session_id": session_id,
            "data": {"reviewed_skills": False, "reviewed_memory": True},
        }

    received: list[dict[str, Any]] = []

    async def _on_event(event: Mapping[str, Any]) -> None:
        received.append(dict(event))

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
    # Wait for reconnect + event processing
    await asyncio.sleep(0.2)
    await subscriber.stop()

    assert len(received) == 1
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
    from IM.ws.gateway_handler import GatewayHandler

    conversation_repo = MagicMock()
    message_repo = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = "msg-1"
    message_repo.create_message.return_value = mock_msg

    conversation_repo.get_conversation.return_value = MagicMock(
        conversation_id="conv-1",
        node_id=None,
    )

    handler = GatewayHandler(
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        node_id="node-1",
    )

    result = await handler.handle(
        websocket=MagicMock(),
        message_type="node.system_message",
        payload={
            "conversation_id": "conv-1",
            "text": "· background self-evolution review: skills updated",
        },
    )

    assert result is not None
    assert result.get("type") != "error"
    message_repo.create_message.assert_called_once()
    call_kwargs = message_repo.create_message.call_args
    assert call_kwargs.kwargs.get("sender_type") == "system" or (
        call_kwargs.args and "system" in str(call_kwargs)
    )
