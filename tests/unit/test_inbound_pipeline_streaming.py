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

    @pytest.mark.asyncio
    async def test_accepted_phase_preserves_existing_run_context_for_injected_steer(
        self,
    ):
        """bugfix-426-M4 (#140): a steer injects into an ACTIVE run and emits an
        accepted lifecycle with that run's EXISTING run_id. The run already has a live
        bubble context (bubble A's message_id, its streaming kernel_message_id). The
        accepted phase must NOT re-seed/wipe it — otherwise message_id is reset to ""
        and bubble A is orphaned (observer can't finalize it → 120s relay-idle → A
        stuck running/failed, the #140 black-screen symptom)."""
        from personal_assistant.main import _build_relay_lifecycle_callback
        from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
        from personal_assistant.channels.base import InboundMessage

        # The run already has a live bubble (A) streaming when the steer is accepted.
        run_context_store: dict[str, dict[str, str]] = {
            "run-active": {
                "conversation_id": "conv-abc",
                "message_id": "bubble-A",
                "agent_id": "Alpha",
                "kernel_message_id": "kmsg-A",
            }
        }

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
        message.metadata = {"relay_task_id": "task-steer", "agent_id": "Alpha"}

        update = MagicMock(spec=RelayLifecycleUpdate)
        update.phase = "accepted"
        update.run_id = "run-active"  # SAME run_id — the steer reuses the active run
        update.agent_id = "Alpha"

        await callback(message, update)

        ctx = run_context_store["run-active"]
        # Bubble A's context survives — not wiped to "".
        assert ctx["message_id"] == "bubble-A", (
            "injected-steer accepted phase must preserve the active run's bubble context"
        )
        assert ctx["kernel_message_id"] == "kmsg-A"
        # The steer's delivery receipt is still sent (the steer message is acknowledged).
        reporter.send_delivery_receipt.assert_called_once()


class TestAcceptedPhaseSeedsRunContextForNonRelay:
    """Non-relay channels (e.g. feishu) must also seed run_context_store so the
    kernel event observer can sync streaming replies to IM.
    """

    @pytest.mark.asyncio
    async def test_accepted_phase_without_relay_task_id_seeds_run_context(self):
        """A message with no relay_task_id (e.g. from feishu) still populates
        run_context_store; no relay delivery receipt is sent."""
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
        message.external_chat_id = "feishu:cli_a:dm:ou_user1"
        message.metadata = {}  # no relay_task_id

        update = MagicMock(spec=RelayLifecycleUpdate)
        update.phase = "accepted"
        update.run_id = "run-feishu-001"
        update.agent_id = "default-agent"
        update.kernel_session_id = "ksession-1"

        await callback(message, update)

        assert "run-feishu-001" in run_context_store
        ctx = run_context_store["run-feishu-001"]
        assert ctx["conversation_id"] == "feishu:cli_a:dm:ou_user1"
        assert ctx["agent_id"] == "default-agent"
        assert ctx["kernel_session_id"] == "ksession-1"
        assert ctx["message_id"] == ""
        reporter.send_delivery_receipt.assert_not_called()
        manager.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_completed_phase_without_relay_task_id_cleans_run_context(self):
        """A non-relay completed lifecycle must remove the run_context entry."""
        from personal_assistant.main import _build_relay_lifecycle_callback
        from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
        from personal_assistant.channels.base import InboundMessage

        run_context_store: dict[str, dict[str, str]] = {
            "run-feishu-001": {
                "conversation_id": "feishu:cli_a:dm:ou_user1",
                "message_id": "msg-1",
                "agent_id": "default-agent",
            }
        }

        reporter = MagicMock()
        reporter.send_delivery_receipt.return_value = {"type": "delivery_receipt"}

        callback = _build_relay_lifecycle_callback(
            reporter=reporter,
            im_connection_manager_factory=lambda: None,
            run_context_store=run_context_store,
        )

        message = MagicMock(spec=InboundMessage)
        message.external_chat_id = "feishu:cli_a:dm:ou_user1"
        message.metadata = {}

        update = MagicMock(spec=RelayLifecycleUpdate)
        update.phase = "completed"
        update.run_id = "run-feishu-001"
        update.agent_id = "default-agent"

        await callback(message, update)

        assert "run-feishu-001" not in run_context_store
        reporter.send_delivery_receipt.assert_not_called()


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
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": "turn_start",
                    "message_id": "auto-placeholder-111",
                },
            }

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

        coro = observer(
            {
                "event": "assistant_message",
                "content": "The answer is 42.",
                "run_id": "run-001",
            }
        )
        assert asyncio.iscoroutine(coro), (
            "Should return coroutine for direct assistant_message path"
        )
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
    async def test_run_heartbeat_forwards_liveness_delta_to_im(self):
        """bugfix-417-M3 R4: a kernel run_heartbeat event is forwarded to IM as a
        run_heartbeat streaming_delta (advancing last_evt) when a message_id exists."""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "msg-xyz",
                "agent_id": "alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        result = observer(
            {"event": "run_heartbeat", "run_id": "run-001", "source": "permission"}
        )
        assert result is None  # heartbeat schedules a fire-and-forget send
        # Let the scheduled _send task run.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        hb_frames = [p for _, p in send_calls if p.get("kind") == "run_heartbeat"]
        assert len(hb_frames) == 1, (
            f"expected one run_heartbeat delta, got: {send_calls}"
        )
        assert hb_frames[0]["message_id"] == "msg-xyz"
        assert hb_frames[0]["source"] == "permission"

    @pytest.mark.asyncio
    async def test_run_heartbeat_skipped_without_message_id(self):
        """No message_id yet (turn_start not acked) → no orphaned heartbeat delta."""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []
        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "",
                "agent_id": "a",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )
        observer({"event": "run_heartbeat", "run_id": "run-001", "source": "tool"})
        await asyncio.sleep(0)
        assert [p for _, p in send_calls if p.get("kind") == "run_heartbeat"] == []

    @pytest.mark.asyncio
    async def test_direct_assistant_message_updates_run_context_store(self):
        """run_context_store must be updated with ack message_id when turn_start is sent inline."""
        from personal_assistant.main import _build_kernel_event_observer

        manager = MagicMock()
        manager.connected = True

        async def mock_send_json_await_ack(message_type, payload):
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": "turn_start",
                    "message_id": "inline-placeholder-222",
                },
            }

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

        coro = observer(
            {"event": "assistant_message", "content": "Hi!", "run_id": "run-001"}
        )
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
        manager.send_json_await_ack = AsyncMock(
            return_value={
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": "turn_start",
                    "message_id": "agent-msg-999",
                },
            }
        )

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

        observer(
            {
                "event": "assistant_message",
                "content": "The answer is 4.",
                "run_id": "run-001",
            }
        )
        # Let the scheduled tasks run
        await asyncio.sleep(0.05)

        # Find message_delta calls
        delta_calls = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(delta_calls) >= 1, (
            f"Expected message_delta to be sent, got send_calls={send_calls}"
        )
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
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": "turn_start",
                    "message_id": "agent-msg-from-gw",
                },
            }

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        manager.send_json_await_ack = mock_send_json_await_ack

        run_context_store: dict[str, dict[str, str]] = {
            "run-001": {
                "conversation_id": "conv-abc",
                "message_id": "",  # empty = not yet created
                "agent_id": "alpha",
            }
        }

        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer(
            {
                "event": "run_status",
                "status": "running",
                "run_id": "run-001",
            }
        )
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
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": "turn_start",
                    "message_id": "agent-placeholder-555",
                },
            }

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

        coro = observer(
            {
                "event": "run_status",
                "status": "running",
                "run_id": "run-001",
            }
        )
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
            return {
                "type": "ack",
                "payload": {
                    "message_type": "node.streaming_delta",
                    "kind": "turn_start",
                    "message_id": "agent-placeholder-777",
                },
            }

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
        coro = observer(
            {
                "event": "run_status",
                "status": "running",
                "run_id": "run-001",
            }
        )
        # Await the coroutine so turn_start ack updates store before assistant_message fires
        if coro is not None:
            await coro

        # Now send assistant_message: should use the new agent message_id
        observer(
            {
                "event": "assistant_message",
                "content": "The answer is 42.",
                "run_id": "run-001",
            }
        )
        await asyncio.sleep(0.05)

        delta_calls = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(delta_calls) >= 1, f"Expected message_delta, got: {send_calls}"
        assert delta_calls[0]["message_id"] == "agent-placeholder-777", (
            f"message_delta must use agent message_id from turn_start ack, got: {delta_calls[0].get('message_id')}"
        )


# ─── bugfix-410-M2 R3: terminal in-flight tool_call reconcile (#97) ──────────


class TestTerminalToolCallReconcile:
    """When a run terminates abnormally, the observer must close any tool_call that
    received tool_start but never tool_end, badging it with a reason. Already-
    completed tool_calls must not be rewritten."""

    def _manager(self) -> tuple[Any, list[tuple]]:
        send_calls: list[tuple] = []
        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        return manager, send_calls

    def _ctx_store(self) -> dict[str, dict[str, str]]:
        return {
            "run-1": {
                "conversation_id": "conv-1",
                "message_id": "agent-msg-1",
                "agent_id": "alpha",
            }
        }

    @pytest.mark.asyncio
    async def test_reconcile_closes_inflight_toolcall_with_reason(self):
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
        )

        # c1 starts and finishes; c2 starts and never ends (the hung bash).
        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "read"}
        )
        observer(
            {"event": "tool_end", "run_id": "run-1", "call_id": "c1", "name": "read"}
        )
        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c2", "name": "bash"}
        )
        await asyncio.sleep(0.02)
        send_calls.clear()

        # Watchdog-driven terminal reconcile.
        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "timed_out",
            }
        )
        await asyncio.sleep(0.02)

        completed = [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert len(completed) == 1, (
            f"only the in-flight c2 must be reconciled, got: {send_calls}"
        )
        tc = completed[0]["tool_call"]
        assert tc["id"] == "c2"
        assert tc["status"] == "failed"
        assert tc["reason"] == "timed_out"

    @pytest.mark.asyncio
    async def test_reconcile_does_not_rewrite_completed_toolcalls(self):
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
        )

        # Both tools complete normally before the terminal event.
        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "read"}
        )
        observer(
            {"event": "tool_end", "run_id": "run-1", "call_id": "c1", "name": "read"}
        )
        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c2", "name": "bash"}
        )
        observer(
            {
                "event": "tool_end",
                "run_id": "run-1",
                "call_id": "c2",
                "name": "bash",
                "error": "exit 1",
            }
        )
        await asyncio.sleep(0.02)
        send_calls.clear()

        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "interrupted",
            }
        )
        await asyncio.sleep(0.02)

        completed = [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert completed == [], (
            f"no in-flight tool_calls remain; nothing should be reconciled, got: {send_calls}"
        )

    @pytest.mark.asyncio
    async def test_reconcile_reason_interrupted_for_non_timeout(self):
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
        )

        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c9", "name": "edit"}
        )
        await asyncio.sleep(0.02)
        send_calls.clear()

        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "interrupted",
            }
        )
        await asyncio.sleep(0.02)

        completed = [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert len(completed) == 1
        assert completed[0]["tool_call"]["reason"] == "interrupted"
        assert completed[0]["tool_call"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_reconcile_user_interrupt_content_sets_tool_card_output(self):
        """bugfix-417-M5 (#114): a user /stop reconcile carries the CC-identical
        user-attribution content, which becomes the in-flight tool card's output
        (collapsed summary). badge reason stays interrupted (→ 已中断)."""
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
        )

        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "bash"}
        )
        await asyncio.sleep(0.02)
        send_calls.clear()

        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "interrupted",
                "content": "[Request interrupted by user for tool use]",
            }
        )
        await asyncio.sleep(0.02)

        completed = [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert len(completed) == 1
        tc = completed[0]["tool_call"]
        assert tc["status"] == "failed"
        assert tc["reason"] == "interrupted"
        assert tc["output"] == "[Request interrupted by user for tool use]"

    @pytest.mark.asyncio
    async def test_reconcile_without_content_omits_tool_card_output(self):
        """A system reap (no content) must NOT set output — the card shows no
        user-attributed body, only the 已中断 badge."""
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
        )

        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "bash"}
        )
        await asyncio.sleep(0.02)
        send_calls.clear()

        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "stalled",
            }
        )
        await asyncio.sleep(0.02)

        completed = [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert len(completed) == 1
        assert "output" not in completed[0]["tool_call"]

    @pytest.mark.asyncio
    async def test_normal_completion_leaves_no_run_entry(self):
        """bugfix-410-fix-r1 (Eff-3): a run that completes normally (tool_end then
        turn_end, no reconcile) must not leak an empty per-run dict entry. A long-lived
        Gateway processes many runs; one residual entry per run is an unbounded leak."""
        from personal_assistant.main import _build_kernel_event_observer

        manager, _ = self._manager()
        # Injected so we can assert the map is reaped — no production caller passes it.
        running_tool_calls: dict[str, dict[str, dict[str, object]]] = {}
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
            running_tool_calls=running_tool_calls,
        )

        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "read"}
        )
        assert "run-1" in running_tool_calls

        # Closing the last in-flight call drops the run_id entry immediately.
        observer(
            {"event": "tool_end", "run_id": "run-1", "call_id": "c1", "name": "read"}
        )
        assert "run-1" not in running_tool_calls

        # turn_end is the normal terminus and re-reaps as a backstop (idempotent).
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await asyncio.sleep(0.02)
        assert running_tool_calls == {}, (
            f"normal completion must leave no residual run entry, got: {running_tool_calls}"
        )

    @pytest.mark.asyncio
    async def test_turn_end_backstops_run_entry_without_tool_end(self):
        """bugfix-410-fix-r1: even if a tool_call's tool_end never arrives on the normal
        path, turn_end must still reap the per-run entry so the map cannot grow."""
        from personal_assistant.main import _build_kernel_event_observer

        manager, _ = self._manager()
        running_tool_calls: dict[str, dict[str, dict[str, object]]] = {}
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
            running_tool_calls=running_tool_calls,
        )

        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "bash"}
        )
        # bugfix-416 #111: the in-flight entry now stores the full call (name + input)
        # so a reconcile can re-emit the original command — not just the bare name.
        assert running_tool_calls.get("run-1") == {"c1": {"name": "bash", "input": {}}}

        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await asyncio.sleep(0.02)
        assert "run-1" not in running_tool_calls

    @pytest.mark.asyncio
    async def test_user_stop_reconcile_finalizes_bubble_and_closes_badge(self):
        """bugfix-417-fix2 (#114, Issue 1): the kernel emits NO turn_end on the cancel
        path, so a user /stop would leave the agent bubble stuck on the running spinner.
        The Gateway marks the reconcile finalize_bubble for a user /stop; the observer
        then closes the in-flight tool badge (已中断 + CC content) AND finalizes the
        bubble with message_completed/delivery_status=completed (clean user stop)."""
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        running_tool_calls: dict[str, dict[str, dict[str, object]]] = {}
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
            running_tool_calls=running_tool_calls,
        )

        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "bash"}
        )
        send_calls.clear()
        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "interrupted",
                "content": "[Request interrupted by user for tool use]",
                "finalize_bubble": True,
            }
        )
        await asyncio.sleep(0.02)

        # Badge closed with CC content.
        tc_done = [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert len(tc_done) == 1
        assert tc_done[0]["tool_call"]["reason"] == "interrupted"
        assert (
            tc_done[0]["tool_call"]["output"]
            == "[Request interrupted by user for tool use]"
        )
        # Bubble finalized (clean stop).
        completed = [p for _, p in send_calls if p.get("kind") == "message_completed"]
        assert len(completed) == 1
        assert completed[0]["message_id"] == "agent-msg-1"
        assert completed[0]["delivery_status"] == "completed"
        # In-flight entry reaped by the reconcile.
        assert "run-1" not in running_tool_calls

    @pytest.mark.asyncio
    async def test_system_reconcile_does_not_finalize_bubble(self):
        """A watchdog/crash reconcile (no finalize_bubble) closes the tool badge but
        must NOT finalize the bubble as completed — the bubble stays failed via the
        phase=failed lifecycle (Req B no-regression)."""
        from personal_assistant.main import _build_kernel_event_observer

        manager, send_calls = self._manager()
        running_tool_calls: dict[str, dict[str, dict[str, object]]] = {}
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=self._ctx_store(),
            running_tool_calls=running_tool_calls,
        )
        observer(
            {"event": "tool_start", "run_id": "run-1", "call_id": "c1", "name": "bash"}
        )
        send_calls.clear()
        observer(
            {"event": "run_terminal_reconcile", "run_id": "run-1", "reason": "stalled"}
        )
        await asyncio.sleep(0.02)

        # Badge closed, but NO bubble finalization (no finalize_bubble flag).
        assert [p for _, p in send_calls if p.get("kind") == "tool_call_completed"]
        assert not [p for _, p in send_calls if p.get("kind") == "message_completed"]


class TestTurnEndCachePassthrough:
    """feat-439-M1 R2: gateway turn_end → message_completed 的 token_usage 白名单
    必须显式带上缓存命中两字段(否则前端永远拿不到、命中率恒 0%)。"""

    @pytest.mark.asyncio
    async def test_turn_end_token_usage_carries_cache_fields(self):
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []
        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        ctx_store = {
            "run-1": {
                "conversation_id": "conv-1",
                "message_id": "agent-msg-1",
                "agent_id": "alpha",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=ctx_store,
        )

        observer(
            {
                "event": "turn_end",
                "run_id": "run-1",
                "completed": True,
                "usage": {
                    "prompt_tokens": 400,
                    "completion_tokens": 15,
                    "total_tokens": 415,
                    "cache_read_tokens": 270,
                    "cache_total_input_tokens": 400,
                },
                "context_window": 200000,
            }
        )
        await asyncio.sleep(0.05)

        completed = [p for _, p in send_calls if p.get("kind") == "message_completed"]
        assert completed, f"expected message_completed, got {send_calls}"
        tu = completed[0]["token_usage"]
        assert tu is not None
        # prompt/completion 不变
        assert tu["prompt"] == 400
        assert tu["completion"] == 15
        # 缓存两字段透传
        assert tu["cache_read"] == 270
        assert tu["cache_total_input"] == 400

    @pytest.mark.asyncio
    async def test_turn_end_without_cache_omits_or_zeroes(self):
        """旧内核/无缓存信息：usage 不带 cache 字段时，payload cache 字段为 0(不崩)。"""
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []
        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        ctx_store = {
            "run-1": {
                "conversation_id": "conv-1",
                "message_id": "agent-msg-1",
                "agent_id": "alpha",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=ctx_store,
        )

        observer(
            {
                "event": "turn_end",
                "run_id": "run-1",
                "completed": True,
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 5,
                    "total_tokens": 105,
                },
            }
        )
        await asyncio.sleep(0.05)

        completed = [p for _, p in send_calls if p.get("kind") == "message_completed"]
        assert completed
        tu = completed[0]["token_usage"]
        assert tu is not None
        assert tu["cache_read"] == 0
        assert tu["cache_total_input"] == 0


# ─── feat-439-M2: observer forwards thinking process items ───────────────────


class TestObserverForwardsThinkingSegment:
    """空正文但有 reasoning 的回合不再丢弃，作为「过程项」转发到当前气泡。"""

    def _manager_with_sink(self, send_calls: list[tuple]):
        manager = MagicMock()
        manager.connected = True

        async def mock_send_json(message_type, payload):
            send_calls.append((message_type, payload))

        manager.send_json = mock_send_json
        manager.send_json_await_ack = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_empty_content_with_reasoning_forwards_thinking_segment(self):
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []
        manager = self._manager_with_sink(send_calls)
        run_context_store = {
            "run-1": {
                "conversation_id": "conv-a",
                "message_id": "agent-msg-1",
                "agent_id": "Alpha",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer(
            {
                "event": "assistant_message",
                "content": "",
                "reasoning_content": "先看 types.py 再动手",
                "message_id": "kernel-1",
                "run_id": "run-1",
            }
        )
        if coro is not None:
            await coro
        await asyncio.sleep(0.05)

        thinking = [p for _, p in send_calls if p.get("kind") == "thinking_segment"]
        assert len(thinking) == 1, f"应转发 1 个 thinking_segment, got {send_calls}"
        assert thinking[0]["message_id"] == "agent-msg-1"
        assert thinking[0]["text"] == "先看 types.py 再动手"
        # 空正文回合不发 delta、不 roll 新气泡
        assert [p for _, p in send_calls if p.get("kind") == "message_delta"] == []
        assert [p for _, p in send_calls if p.get("kind") == "turn_start"] == []

    @pytest.mark.asyncio
    async def test_empty_content_no_reasoning_is_dropped(self):
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []
        manager = self._manager_with_sink(send_calls)
        run_context_store = {
            "run-1": {
                "conversation_id": "conv-a",
                "message_id": "agent-msg-1",
                "agent_id": "Alpha",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer(
            {
                "event": "assistant_message",
                "content": "",
                "reasoning_content": "",
                "message_id": "kernel-1",
                "run_id": "run-1",
            }
        )
        assert coro is None, "空正文+无 reasoning 的回合必须丢弃(return None)"
        await asyncio.sleep(0.05)
        assert send_calls == []

    @pytest.mark.asyncio
    async def test_content_with_reasoning_forwards_both(self):
        from personal_assistant.main import _build_kernel_event_observer

        send_calls: list[tuple] = []
        manager = self._manager_with_sink(send_calls)
        run_context_store = {
            "run-1": {
                "conversation_id": "conv-a",
                "message_id": "agent-msg-1",
                "agent_id": "Alpha",
            }
        }
        observer = _build_kernel_event_observer(
            im_connection_manager_factory=lambda: manager,
            run_context_store=run_context_store,
        )

        coro = observer(
            {
                "event": "assistant_message",
                "content": "答案是 4",
                "reasoning_content": "最后再想一下",
                "message_id": "kernel-1",
                "run_id": "run-1",
            }
        )
        if coro is not None:
            await coro
        await asyncio.sleep(0.05)

        thinking = [p for _, p in send_calls if p.get("kind") == "thinking_segment"]
        delta = [p for _, p in send_calls if p.get("kind") == "message_delta"]
        assert len(thinking) == 1 and thinking[0]["text"] == "最后再想一下"
        assert len(delta) == 1 and delta[0]["delta_text"] == "答案是 4"
        assert thinking[0]["message_id"] == "agent-msg-1"
        assert delta[0]["message_id"] == "agent-msg-1"
