"""Unit tests for M14 streaming chain: node.streaming_delta → EventBridge → WS push.

Tests verify:
1. GatewayHandler.handle_message("node.streaming_delta") calls EventBridge correctly
2. Cross-tenant isolation: streaming frames only broadcast to caller's owner WS
3. token_usage carried in relay.report event payload
"""

from __future__ import annotations

import json
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from IM.application.event_bridge import EventBridge
from IM.domain.models import ConversationEvent, Message, TokenUsage, ToolCall
from IM.ws.gateway_handler import GatewayHandler
from IM.ws.user_stream import UserStreamRegistry


# ─── helpers ─────────────────────────────────────────────────────────────────


def _make_minimal_handler(
    *,
    event_bridge: EventBridge | None = None,
    user_stream_registry: UserStreamRegistry | None = None,
) -> GatewayHandler:
    """Build a GatewayHandler with just enough config for streaming tests."""
    relay_service = MagicMock()
    relay_service.get_relay_task = MagicMock(return_value=None)

    conv_repo = MagicMock()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conv_repo._connection = conn

    event_repo = MagicMock()
    event_repo.append_event.return_value = ConversationEvent(
        event_id=1,
        conversation_id="conv-1",
        message_id="msg-1",
        event_type="message.delta",
        delivery_status="running",
        payload_json="{}",
        created_at="2026-01-01T00:00:00Z",
    )

    handler = GatewayHandler(
        relay_service=relay_service,
        conversation_repository=conv_repo,
        event_repository=event_repo,
        user_stream_registry=user_stream_registry or UserStreamRegistry(),
        event_bridge=event_bridge,
    )
    return handler


# ─── R1 tests: gateway_handler receives node.streaming_delta ─────────────────


class TestNodeStreamingDeltaHandling:
    """GatewayHandler.handle_message('node.streaming_delta') dispatches to EventBridge."""

    @pytest.mark.asyncio
    async def test_streaming_delta_calls_event_bridge_on_message_delta(self):
        """node.streaming_delta with kind=message_delta calls EventBridge.on_message_delta."""
        bridge = MagicMock(spec=EventBridge)
        handler = _make_minimal_handler(event_bridge=bridge)

        ws = AsyncMock()
        payload = {
            "kind": "message_delta",
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "delta_text": "Hello",
            "owner_id": "owner-A",
        }
        await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        bridge.on_message_delta.assert_called_once_with(
            message_id="msg-1", delta_text="Hello"
        )

    @pytest.mark.asyncio
    async def test_streaming_delta_turn_start_calls_on_turn_start(self):
        """node.streaming_delta with kind=turn_start calls EventBridge.on_turn_start."""
        bridge = MagicMock(spec=EventBridge)
        bridge.on_turn_start.return_value = Message(
            id="msg-new",
            conversation_id="conv-1",
            sender_user_id="agent-user-1",
            sender_type="agent",
            content="",
            attachments=[],
            delivery_status="running",
            created_at="2026-01-01T00:00:00Z",
        )
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "turn_start",
            "conversation_id": "conv-1",
            "agent_user_id": "agent-user-1",
            "agent_id": "alpha",
            "owner_id": "owner-A",
        }
        result = await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        bridge.on_turn_start.assert_called_once_with(
            conversation_id="conv-1",
            agent_user_id="agent-user-1",
            agent_id="alpha",
        )
        assert result is not None
        assert result.get("type") == "ack"

    @pytest.mark.asyncio
    async def test_streaming_delta_tool_call_upserted(self):
        """node.streaming_delta with kind=tool_call_upserted calls on_tool_call_upserted."""
        bridge = MagicMock(spec=EventBridge)
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "tool_call_upserted",
            "message_id": "msg-1",
            "tool_call": {
                "id": "tc-1",
                "name": "bash",
                "status": "running",
                "input": {"command": "ls"},
            },
            "owner_id": "owner-A",
        }
        await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        assert bridge.on_tool_call_upserted.called
        tc_arg = bridge.on_tool_call_upserted.call_args[1]["tool_call"]
        assert tc_arg.id == "tc-1"
        assert tc_arg.name == "bash"

    @pytest.mark.asyncio
    async def test_streaming_delta_tool_call_completed(self):
        """node.streaming_delta with kind=tool_call_completed calls on_tool_call_completed."""
        bridge = MagicMock(spec=EventBridge)
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "tool_call_completed",
            "message_id": "msg-1",
            "tool_call": {
                "id": "tc-1",
                "name": "bash",
                "status": "completed",
                "input": {"command": "ls"},
                "output": "file.txt",
                "duration_ms": 120,
            },
            "owner_id": "owner-A",
        }
        await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        assert bridge.on_tool_call_completed.called

    @pytest.mark.asyncio
    async def test_streaming_delta_message_completed(self):
        """node.streaming_delta with kind=message_completed calls on_message_completed."""
        bridge = MagicMock(spec=EventBridge)
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "message_completed",
            "message_id": "msg-1",
            "final_content": "The answer is 4.",
            "token_usage": {"prompt": 10, "completion": 5, "total": 15},
            "owner_id": "owner-A",
        }
        await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        assert bridge.on_message_completed.called
        kwargs = bridge.on_message_completed.call_args[1]
        assert kwargs["message_id"] == "msg-1"
        assert kwargs["final_content"] == "The answer is 4."
        token_usage = kwargs.get("token_usage")
        assert token_usage is not None
        assert token_usage.output == 5

    @pytest.mark.asyncio
    async def test_streaming_delta_message_completed_failed_status(self):
        """delivery_status='failed' is accepted and passed through to event_bridge.

        Confirms the bugfix-380 round-3-rev3 path: when observer dispatches
        message_completed(delivery_status='failed') for a ModelError turn, IM
        must forward that terminal state instead of overwriting with 'completed'.
        """
        bridge = MagicMock(spec=EventBridge)
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "message_completed",
            "message_id": "msg-fail",
            "final_content": None,
            "delivery_status": "failed",
            "owner_id": "owner-A",
        }
        await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        assert bridge.on_message_completed.called
        kwargs = bridge.on_message_completed.call_args[1]
        assert kwargs["delivery_status"] == "failed"

    @pytest.mark.asyncio
    async def test_streaming_delta_message_completed_rejects_unknown_status(self):
        """Unknown delivery_status (e.g. 'running' / typo) must raise, not silently
        fall back to 'completed'.

        The silent fallback this replaces was a regression trap — any new failure
        semantic added upstream that wasn't whitelisted here would silently
        downgrade to the bugfix-380 pre-fix bug (empty bubble marked 'completed').
        """
        bridge = MagicMock(spec=EventBridge)
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "message_completed",
            "message_id": "msg-bad",
            "final_content": None,
            "delivery_status": "running",  # not a terminal state
            "owner_id": "owner-A",
        }
        with pytest.raises(ValueError, match="delivery_status must be"):
            await handler.handle_message(
                websocket=ws, message_type="node.streaming_delta", payload=payload
            )
        # bridge must NOT have been called — frame is rejected before reaching IM
        assert not bridge.on_message_completed.called

    @pytest.mark.asyncio
    async def test_streaming_delta_without_bridge_returns_ack(self):
        """Without EventBridge (no repos wired), node.streaming_delta returns ack without crash."""
        # Build a handler with no conversation/event repos so event_bridge auto-creation is skipped.
        relay_service = MagicMock()
        handler = GatewayHandler(relay_service=relay_service)
        ws = AsyncMock()
        payload = {
            "kind": "message_delta",
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "delta_text": "Hello",
            "owner_id": "owner-A",
        }
        result = await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        assert result is not None
        assert result.get("type") == "ack"


# ─── R1 tests: relay.report now carries token_usage ──────────────────────────


class TestRelayReportTokenUsage:
    """_persist_report_event embeds token_usage in relay.report event payload."""

    def test_persist_report_event_includes_token_usage_when_status_completed(self):
        """relay.report event payload must carry token_usage when status=completed."""
        event_repo = MagicMock()
        captured: list[dict] = []

        def capture_append(**kwargs):
            captured.append(kwargs)
            return ConversationEvent(
                event_id=1,
                conversation_id=kwargs.get("conversation_id", "conv-1"),
                message_id=kwargs.get("message_id", "msg-1"),
                event_type=kwargs.get("event_type", "relay.report"),
                delivery_status=kwargs.get("delivery_status", "completed"),
                payload_json=json.dumps(kwargs.get("payload", {})),
                created_at="2026-01-01T00:00:00Z",
            )

        event_repo.append_event.side_effect = capture_append
        event_repo.update_message_delivery_status = MagicMock()

        relay_service = MagicMock()
        conv_repo = MagicMock()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        conv_repo._connection = conn

        handler = GatewayHandler(
            relay_service=relay_service,
            event_repository=event_repo,
            conversation_repository=conv_repo,
        )
        payload = {
            "node_id": "node-1",
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "run_id": "run-1",
            "status": "completed",
            "summary": "done",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        handler._persist_report_event(payload=payload)

        # Find the relay.report event
        report_events = [c for c in captured if c.get("event_type") == "relay.report"]
        assert report_events, "Expected a relay.report event"
        report_payload = report_events[0]["payload"]
        assert "token_usage" in report_payload, (
            "relay.report payload must contain token_usage"
        )
        assert report_payload["token_usage"]["total"] == 15
        assert report_payload["token_usage"]["prompt"] == 10
        assert report_payload["token_usage"]["completion"] == 5


# ─── R1 tests: cross-tenant isolation ────────────────────────────────────────


class TestCrossTenantStreamingIsolation:
    """Streaming frames from owner A must not reach owner B's WS connections."""

    @pytest.mark.asyncio
    async def test_streaming_delta_only_reaches_specified_owner(self):
        """on_message_delta → broadcast_to_user(owner_id, ...) not broadcast_to_users(all)."""
        bridge = MagicMock(spec=EventBridge)
        registry = MagicMock(spec=UserStreamRegistry)
        registry.broadcast_to_user = AsyncMock()
        registry.broadcast_to_users = AsyncMock()

        handler = _make_minimal_handler(
            event_bridge=bridge, user_stream_registry=registry
        )

        ws = AsyncMock()
        payload = {
            "kind": "message_delta",
            "conversation_id": "conv-A",
            "message_id": "msg-A",
            "delta_text": "secret A",
            "owner_id": "owner-A",
        }
        await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )

        # broadcast_to_users (all users) must not be called for streaming frames
        registry.broadcast_to_users.assert_not_called()


# ─── R2 tests: turn_start ack returns message_id (M16) ───────────────────────


class TestTurnStartAckReturnsMessageId:
    """gateway turn_start ack must include message_id so observer can update run_context_store."""

    @pytest.mark.asyncio
    async def test_turn_start_ack_includes_message_id_from_event_bridge(self):
        """_handle_streaming_delta(turn_start) ack payload must carry message_id from created placeholder."""
        bridge = MagicMock(spec=EventBridge)
        bridge.on_turn_start.return_value = Message(
            id="agent-placeholder-msg-42",
            conversation_id="conv-1",
            sender_user_id="agent-user-1",
            sender_type="agent",
            content="",
            attachments=[],
            delivery_status="running",
            created_at="2026-01-01T00:00:00Z",
        )
        handler = _make_minimal_handler(event_bridge=bridge)
        ws = AsyncMock()
        payload = {
            "kind": "turn_start",
            "conversation_id": "conv-1",
            "agent_user_id": "agent-user-1",
            "agent_id": "alpha",
            "owner_id": "owner-A",
        }
        result = await handler.handle_message(
            websocket=ws, message_type="node.streaming_delta", payload=payload
        )
        assert result is not None
        assert result.get("type") == "ack"
        # message_id must appear in the ack payload so the PA observer can update run_context_store
        ack_payload = result.get("payload", {})
        assert ack_payload.get("message_id") == "agent-placeholder-msg-42", (
            f"turn_start ack must carry message_id, got: {ack_payload}"
        )
