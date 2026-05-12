"""Unit tests for M16: streaming agent placeholder creation via turn_start ack.

Verifies that:
1. On relay_lifecycle accepted phase, run_context_store is seeded with empty message_id
   (no more REST pre-creation via im_http_client — that path used wrong agent_user_id).
2. kernel_event_observer sends turn_start frame on run_status=running and updates
   run_context_store with the message_id from the gateway ack.
3. message_delta uses the agent message_id from run_context_store (not user message_id).
"""

from __future__ import annotations

from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock
import asyncio

import pytest


# ─── R1 tests: accepted phase seeds run_context_store ────────────────────────


class TestAcceptedPhaseSeedsRunContext:
    """When relay_lifecycle phase=accepted, run_context_store is seeded with empty message_id."""

    @pytest.mark.asyncio
    async def test_accepted_phase_seeds_run_context_with_empty_message_id(self):
        """Accepted phase must populate run_context_store with conversation/agent but empty message_id."""
        from personal_assistant.main import _build_relay_lifecycle_callback
        from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
        from personal_assistant.channels.base import InboundMessage

        run_context_store: dict[str, dict[str, str]] = {}

        manager = MagicMock()
        manager.connected = True
        manager.send_json = AsyncMock()

        reporter = MagicMock()
        reporter.send_delivery_receipt.return_value = {"type": "delivery_receipt"}

        callback = _build_relay_lifecycle_callback(
            reporter=reporter,
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        message = MagicMock(spec=InboundMessage)
        message.external_chat_id = "conv-abc"
        message.metadata = {
            "relay_task_id": "task-1",
            "message_id": "user-msg-001",
            "agent_id": "Alpha",
        }

        update = MagicMock(spec=RelayLifecycleUpdate)
        update.phase = "accepted"
        update.run_id = "run-001"
        update.agent_id = "Alpha"

        await callback(message, update)

        assert "run-001" in run_context_store
        ctx = run_context_store["run-001"]
        assert ctx["conversation_id"] == "conv-abc"
        assert ctx["agent_id"] == "Alpha"
        # message_id starts empty; it will be filled by turn_start ack
        assert ctx["message_id"] == "", (
            f"message_id must be empty initially (filled by turn_start ack), got: '{ctx['message_id']}'"
        )

    @pytest.mark.asyncio
    async def test_accepted_phase_does_not_store_user_message_id(self):
        """Accepted phase must NOT store user message_id as the agent message_id."""
        from personal_assistant.main import _build_relay_lifecycle_callback
        from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
        from personal_assistant.channels.base import InboundMessage

        run_context_store: dict[str, dict[str, str]] = {}

        manager = MagicMock()
        manager.connected = True
        manager.send_json = AsyncMock()

        reporter = MagicMock()
        reporter.send_delivery_receipt.return_value = {"type": "delivery_receipt"}

        callback = _build_relay_lifecycle_callback(
            reporter=reporter,
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        message = MagicMock(spec=InboundMessage)
        message.external_chat_id = "conv-abc"
        message.metadata = {
            "relay_task_id": "task-1",
            "message_id": "user-msg-001",  # user message id must NOT end up in store
            "agent_id": "Alpha",
        }

        update = MagicMock(spec=RelayLifecycleUpdate)
        update.phase = "accepted"
        update.run_id = "run-001"
        update.agent_id = "Alpha"

        await callback(message, update)

        ctx = run_context_store.get("run-001", {})
        assert ctx.get("message_id") != "user-msg-001", (
            "accepted phase must not store user message_id as agent message_id"
        )


# ─── R2b tests: kernel skips run_status=running (direct assistant_message) ───


class TestObserverHandlesDirectAssistantMessage:
    """When kernel emits assistant_message without prior run_status=running,
    observer must send turn_start inline then message_delta."""

    @pytest.mark.asyncio
    async def test_direct_assistant_message_sends_turn_start_then_delta(self):
        """assistant_message with empty message_id triggers turn_start + delta as one awaitable."""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json_await_ack(message_type, payload):
            send_calls.append((message_type, payload))
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta", "kind": "turn_start", "message_id": "auto-placeholder-111"}}

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        manager.send_json_await_ack = mock_send_json_await_ack

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "",  # empty: no run_status=running was emitted
                "agent_id": "alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer({
            "event": "assistant_message",
            "content": "The answer is 42.",
            "run_id": "run-001",
        })
        assert asyncio.iscoroutine(coro), "Should return coroutine for direct assistant_message path"
        await coro

        # turn_start must have been sent
        turn_start_frames = [p for _, p in send_calls if p.get("kind") == "turn_start"]
        assert len(turn_start_frames) >= 1, f"Expected turn_start, got: {send_calls}"

        # delta must have been sent with the ack'd message_id
        delta_frames = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(delta_frames) >= 1, f"Expected message_delta, got: {send_calls}"
        assert delta_frames[0]["message_id"] == "auto-placeholder-111"
        assert delta_frames[0]["delta_text"] == "The answer is 42."

    @pytest.mark.asyncio
    async def test_direct_assistant_message_updates_run_context_store(self):
        """run_context_store must be updated with ack message_id when turn_start is sent inline."""
        from personal_assistant.main import _build_kernel_event_observer

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json_await_ack(message_type, payload):
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta", "kind": "turn_start", "message_id": "inline-placeholder-222"}}

        manager.send_json = AsyncMock()
        manager.send_json_await_ack = mock_send_json_await_ack

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {"conversation_id": "conv-abc", "message_id": "", "agent_id": "alpha"}
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer({"event": "assistant_message", "content": "Hi!", "run_id": "run-001"})
        if coro is not None:
            await coro

        assert run_context_store["run-001"]["message_id"] == "inline-placeholder-222"


# ─── R2 tests: kernel_event_observer sends turn_start (M16) ──────────────────


class TestObserverSendsTurnStart:
    """kernel_event_observer must send turn_start frame on run_status=running."""

    @pytest.mark.asyncio
    async def test_observer_uses_agent_message_id_for_delta(self):
        """message_delta uses the agent message_id from run_context_store."""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        manager.send_json_await_ack = AsyncMock(return_value={
            "type": "ack",
            "payload": {"message_type": "node.streaming_delta", "kind": "turn_start", "message_id": "agent-msg-999"},
        })

        run_context_store = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "agent-msg-999",
                "agent_id": "Alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        observer({
            "event": "assistant_message",
            "content": "The answer is 4.",
            "run_id": "run-001",
        })
        # Let the scheduled tasks run
        await asyncio.sleep(0.05)

        # Find message_delta calls
        delta_calls = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(delta_calls) >= 1, f"Expected message_delta to be sent, got send_calls={send_calls}"
        assert delta_calls[0]["message_id"] == "agent-msg-999", (
            f"message_delta must use agent message_id, got {delta_calls[0].get('message_id')}"
        )


# ─── R2 tests: observer sends turn_start + updates run_context_store (M16) ────


class TestObserverSendsTurnStartAndUpdatesStore:
    """Observer must send turn_start frame and update run_context_store with ack message_id."""

    @pytest.mark.asyncio
    async def test_observer_sends_turn_start_on_run_status_running(self):
        """run_status=running must emit kind=turn_start frame to gateway."""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json_await_ack(message_type, payload):
            send_calls.append((message_type, payload))
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta", "kind": "turn_start", "message_id": "agent-msg-from-gw"}}

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        manager.send_json_await_ack = mock_send_json_await_ack

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "",   # empty = not yet created
                "agent_id": "alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer({
            "event": "run_status",
            "status": "running",
            "run_id": "run-001",
        })
        if coro is not None:
            await coro
        await asyncio.sleep(0.05)

        turn_start_frames = [p for _, p in send_calls if p.get("kind") == "turn_start"]
        assert len(turn_start_frames) >= 1, (
            f"Observer must send turn_start on run_status=running, got: {send_calls}"
        )

    @pytest.mark.asyncio
    async def test_observer_updates_run_context_store_with_ack_message_id(self):
        """After turn_start ack, run_context_store must have the agent message_id from ack."""
        from personal_assistant.main import _build_kernel_event_observer

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json_await_ack(message_type, payload):
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta", "kind": "turn_start", "message_id": "agent-placeholder-555"}}

        manager.send_json = AsyncMock()
        manager.send_json_await_ack = mock_send_json_await_ack

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "",
                "agent_id": "alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer({
            "event": "run_status",
            "status": "running",
            "run_id": "run-001",
        })
        if coro is not None:
            await coro

        assert run_context_store["run-001"]["message_id"] == "agent-placeholder-555", (
            f"run_context_store must be updated with ack message_id, got: {run_context_store}"
        )

    @pytest.mark.asyncio
    async def test_delta_uses_message_id_from_turn_start_ack(self):
        """After turn_start ack updates run_context_store, message_delta must use the new message_id."""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json_await_ack(message_type, payload):
            return {"type": "ack", "payload": {"message_type": "node.streaming_delta", "kind": "turn_start", "message_id": "agent-placeholder-777"}}

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        manager.send_json_await_ack = mock_send_json_await_ack

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "",
                "agent_id": "alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        # Simulate run_status=running (sends turn_start and updates store)
        coro = observer({
            "event": "run_status",
            "status": "running",
            "run_id": "run-001",
        })
        # Await the coroutine so turn_start ack updates store before assistant_message fires
        if coro is not None:
            await coro

        # Now send assistant_message: should use the new agent message_id
        observer({
            "event": "assistant_message",
            "content": "The answer is 42.",
            "run_id": "run-001",
        })
        await asyncio.sleep(0.05)

        delta_calls = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(delta_calls) >= 1, f"Expected message_delta, got: {send_calls}"
        assert delta_calls[0]["message_id"] == "agent-placeholder-777", (
            f"message_delta must use agent message_id from turn_start ack, got: {delta_calls[0].get('message_id')}"
        )
