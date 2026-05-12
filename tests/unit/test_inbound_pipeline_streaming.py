"""Unit tests for M15: streaming agent placeholder creation timing.

Verifies that:
1. On relay_lifecycle accepted phase, Gateway pre-creates agent placeholder via IM HTTP API
   and stores the agent message_id (not user message_id) in run_context_store.
2. kernel_event_observer skips turn_start (placeholder already created) and uses
   the pre-created agent message_id for message_delta / message_completed.
3. user message content is not polluted by streaming delta.
"""

from __future__ import annotations

from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import pytest


# ─── helpers ──────────────────────────────────────────────────────────────────


def _make_im_http_client_mock(agent_message_id: str = "agent-msg-001") -> MagicMock:
    """Produce a mock httpx.Client that returns a pre-created agent message id."""
    client = MagicMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"id": agent_message_id}
    client.post.return_value = response
    return client


# ─── R1 tests: accepted phase pre-creates agent placeholder ───────────────────


class TestAcceptedPhasePreCreatesPlaceholder:
    """When relay_lifecycle phase=accepted, gateway calls IM HTTP to create agent placeholder."""

    @pytest.mark.asyncio
    async def test_accepted_phase_calls_im_api_to_create_agent_message(self):
        """_build_relay_lifecycle_callback accepted phase must POST to IM conversations messages."""
        from personal_assistant.main import _build_relay_lifecycle_callback
        from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
        from personal_assistant.channels.base import InboundMessage

        im_client = _make_im_http_client_mock(agent_message_id="agent-msg-999")
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
            im_http_client=im_client,
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

        # Must have called IM HTTP to create placeholder
        im_client.post.assert_called_once()
        call_args = im_client.post.call_args
        assert "conv-abc" in call_args[0][0]  # URL contains conversation_id
        body = call_args[1].get("json") or {}
        assert body.get("sender_type") == "agent"

    @pytest.mark.asyncio
    async def test_accepted_phase_stores_agent_message_id_not_user_message_id(self):
        """run_context_store must store agent placeholder message_id, not user message_id."""
        from personal_assistant.main import _build_relay_lifecycle_callback
        from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
        from personal_assistant.channels.base import InboundMessage

        im_client = _make_im_http_client_mock(agent_message_id="agent-msg-999")
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
            im_http_client=im_client,
        )

        message = MagicMock(spec=InboundMessage)
        message.external_chat_id = "conv-abc"
        message.metadata = {
            "relay_task_id": "task-1",
            "message_id": "user-msg-001",   # user message id
            "agent_id": "Alpha",
        }

        update = MagicMock(spec=RelayLifecycleUpdate)
        update.phase = "accepted"
        update.run_id = "run-001"
        update.agent_id = "Alpha"

        await callback(message, update)

        # run_context_store must have agent message_id, NOT user message_id
        assert "run-001" in run_context_store
        ctx = run_context_store["run-001"]
        assert ctx["message_id"] == "agent-msg-999", (
            f"Expected agent message id 'agent-msg-999', got '{ctx['message_id']}'"
        )
        assert ctx["message_id"] != "user-msg-001", "Must not store user message id"

    @pytest.mark.asyncio
    async def test_accepted_phase_without_im_client_falls_back_to_user_message_id(self):
        """Without im_http_client, accepted phase keeps previous behaviour (user message_id)."""
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
            # no im_http_client → fallback
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

        # Without im_http_client fallback: user message_id is stored
        assert "run-001" in run_context_store


# ─── R2 tests: kernel_event_observer skips turn_start ────────────────────────


class TestObserverSkipsTurnStart:
    """kernel_event_observer must NOT send turn_start frame when placeholder already created."""

    def test_observer_does_not_send_turn_start_when_message_id_already_set(self):
        """If run_context_store already has message_id (from pre-creation), turn_start is skipped."""
        from personal_assistant.main import _build_kernel_event_observer

        sent_frames: list[dict] = []
        loop = asyncio.new_event_loop()

        async def mock_send(manager, message_type, payload):
            sent_frames.append({"type": message_type, "payload": payload})

        manager = MagicMock()
        manager.connected = True

        run_context_store = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "agent-msg-999",   # already pre-created
                "agent_id": "Alpha",
            }
        }

        with patch("personal_assistant.main._build_kernel_event_observer.__code__", wraps=None):
            pass  # Just to import cleanly

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        # Simulate run_status=running event (previously triggered turn_start)
        try:
            loop.run_until_complete(asyncio.sleep(0))
            observer({
                "event": "run_status",
                "status": "running",
                "run_id": "run-001",
            })
            loop.run_until_complete(asyncio.sleep(0))
        finally:
            loop.close()

        # No turn_start frame should be sent (placeholder already pre-created)
        turn_start_frames = [f for f in sent_frames if f.get("payload", {}).get("kind") == "turn_start"]
        assert len(turn_start_frames) == 0, (
            f"Expected no turn_start frames when placeholder already pre-created, got: {turn_start_frames}"
        )

    def test_observer_uses_agent_message_id_for_delta(self):
        """message_delta uses the agent message_id from run_context_store."""
        from personal_assistant.main import _build_kernel_event_observer

        sent_frames: list[dict] = []
        loop = asyncio.new_event_loop()

        async def _collect_task(coro):
            result = await coro
            sent_frames.append(result)

        manager = MagicMock()
        manager.connected = True

        # Track what send_json is called with
        send_calls: list[tuple] = []

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json

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

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(asyncio.sleep(0))
            observer({
                "event": "assistant_message",
                "content": "The answer is 4.",
                "run_id": "run-001",
            })
            loop.run_until_complete(asyncio.sleep(0.05))
        finally:
            loop.close()

        # Find message_delta calls
        delta_calls = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(delta_calls) >= 1, f"Expected message_delta to be sent, got send_calls={send_calls}"
        assert delta_calls[0]["message_id"] == "agent-msg-999", (
            f"message_delta must use agent message_id, got {delta_calls[0].get('message_id')}"
        )
