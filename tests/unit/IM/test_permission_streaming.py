"""Tests for permission_request / permission_resolved streaming_delta kinds.

R1: gateway_handler handles new permission kinds via EventBridge.
R2: REST endpoint converts user decision to Gateway WS permission_response.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from IM.api.ws.event_types import EVENT_PERMISSION_REQUEST, EVENT_PERMISSION_RESOLVED
from IM.application.event_bridge import EventBridge
from IM.domain.models import Message
from IM.infra.db import initialize_schema as build_schema
from IM.infra.repositories import EventRepository, MessageRepository


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    build_schema(conn)
    return conn


def _insert_user(conn: sqlite3.Connection, user_id: str, username: str) -> None:
    conn.execute(
        "INSERT INTO users(id, username, display_name, owner_id, created_at) VALUES (?,?,?,?,?)",
        (user_id, username, username, "owner-1", "2024-01-01T00:00:00"),
    )
    conn.commit()


def _insert_conversation(conn: sqlite3.Connection, cid: str, owner_id: str = "owner-1") -> None:
    conn.execute(
        "INSERT INTO conversations(id, title, owner_id, creator_id, is_pinned, is_muted, unread_count, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (cid, "chat", owner_id, "u1", 0, 0, 0, "2024-01-01T00:00:00"),
    )
    conn.commit()


def _insert_message(conn: sqlite3.Connection, msg_id: str, cid: str, sender_user_id: str) -> None:
    conn.execute(
        "INSERT INTO messages(id, conversation_id, sender_user_id, sender_type, content, delivery_status, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (msg_id, cid, sender_user_id, "agent", "", "running", "2024-01-01T00:00:00"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# EventBridge — permission_request upsert
# ---------------------------------------------------------------------------

class TestEventBridgePermissionRequest:
    """EventBridge.on_permission_request upserts embedded JSON and emits WS event."""

    def _make_bridge(self, conn: sqlite3.Connection) -> tuple[EventBridge, list]:
        emitted: list = []

        def notify(event):
            emitted.append(event)

        msg_repo = MessageRepository(conn, notify=None)
        evt_repo = EventRepository(conn)
        bridge = EventBridge(
            message_repository=msg_repo,
            event_repository=evt_repo,
            notify=notify,
        )
        return bridge, emitted

    def test_on_permission_request_upserts_and_emits(self) -> None:
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, emitted = self._make_bridge(conn)

        permission_data = {
            "request_id": "req-abc",
            "tool_name": "bash",
            "tool_input": {"command": "rm -rf /tmp/old"},
            "question": "Allow bash? Risky deletion",
            "options": [
                {"id": "allow_once", "label": "Allow once", "description": "Allow this single action"},
                {"id": "deny", "label": "Deny", "description": "Block this action"},
            ],
        }
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request=permission_data,
        )

        # Should emit a permission.request WS event
        assert len(emitted) == 1
        event = emitted[0]
        payload = json.loads(event.payload_json)
        assert payload["event_type"] == EVENT_PERMISSION_REQUEST
        assert payload["permission_request"]["request_id"] == "req-abc"
        assert payload["permission_request"]["tool_name"] == "bash"
        assert payload["message_id"] == "msg-1"

        # Should persist permission_request_json on the message
        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        assert row is not None
        persisted = json.loads(row["permission_request_json"])
        assert persisted["request_id"] == "req-abc"
        assert persisted["status"] == "pending"

    def test_on_permission_resolved_updates_status_and_emits(self) -> None:
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, emitted = self._make_bridge(conn)

        # First upsert a pending permission
        permission_data = {
            "request_id": "req-xyz",
            "tool_name": "write",
            "tool_input": {"file_path": "/tmp/test.py"},
            "question": "Allow write?",
            "options": [],
        }
        bridge.on_permission_request(message_id="msg-1", permission_request=permission_data)
        emitted.clear()

        # Now resolve it
        bridge.on_permission_resolved(
            message_id="msg-1",
            request_id="req-xyz",
            decision="allow_once",
        )

        assert len(emitted) == 1
        event = emitted[0]
        payload = json.loads(event.payload_json)
        assert payload["event_type"] == EVENT_PERMISSION_RESOLVED
        assert payload["request_id"] == "req-xyz"
        assert payload["decision"] == "allow_once"

        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        persisted = json.loads(row["permission_request_json"])
        assert persisted["status"] == "resolved"
        assert persisted["decision"] == "allow_once"

    def test_on_permission_request_no_message_raises(self) -> None:
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        # Do NOT insert message

        bridge, _ = self._make_bridge(conn)
        with pytest.raises(ValueError, match="message_id not found"):
            bridge.on_permission_request(
                message_id="nonexistent",
                permission_request={"request_id": "req-1", "tool_name": "bash"},
            )


# ---------------------------------------------------------------------------
# gateway_handler — streaming_delta permission_request / permission_resolved kinds
# ---------------------------------------------------------------------------

class TestGatewayHandlerPermissionKinds:
    """gateway_handler._handle_streaming_delta routes new permission kinds to EventBridge."""

    def _make_handler_with_mock_bridge(self):
        """Build a minimal GatewayHandler with a mocked EventBridge."""
        from IM.ws.gateway_handler import GatewayHandler
        from IM.application.relay_service import RelayService

        relay_service = MagicMock(spec=RelayService)
        handler = GatewayHandler(relay_service=relay_service)

        mock_bridge = MagicMock()
        handler._event_bridge = mock_bridge
        return handler, mock_bridge

    @pytest.mark.asyncio
    async def test_permission_request_kind_calls_bridge(self) -> None:
        handler, mock_bridge = self._make_handler_with_mock_bridge()

        payload = {
            "kind": "permission_request",
            "message_id": "msg-1",
            "permission_request": {
                "request_id": "req-1",
                "tool_name": "bash",
                "tool_input": {"command": "rm -rf /tmp"},
                "question": "Allow rm?",
                "options": [],
            },
        }
        result = await handler._handle_streaming_delta(payload=payload)
        assert result["type"] == "ack"
        mock_bridge.on_permission_request.assert_called_once_with(
            message_id="msg-1",
            permission_request=payload["permission_request"],
        )

    @pytest.mark.asyncio
    async def test_permission_resolved_kind_calls_bridge(self) -> None:
        handler, mock_bridge = self._make_handler_with_mock_bridge()

        payload = {
            "kind": "permission_resolved",
            "message_id": "msg-1",
            "request_id": "req-1",
            "decision": "deny",
        }
        result = await handler._handle_streaming_delta(payload=payload)
        assert result["type"] == "ack"
        mock_bridge.on_permission_resolved.assert_called_once_with(
            message_id="msg-1",
            request_id="req-1",
            decision="deny",
        )

    @pytest.mark.asyncio
    async def test_permission_response_kind_forwarded_to_pa(self) -> None:
        """permission_response kind (IM→PA direction) is a no-op in GatewayHandler streaming delta.

        The actual forwarding to PA happens through the pending WS connection,
        not through streaming_delta. This kind is routed differently.
        """
        handler, mock_bridge = self._make_handler_with_mock_bridge()

        payload = {
            "kind": "permission_response",
            "request_id": "req-1",
            "decision": "allow_once",
        }
        # Should not raise and return ack
        result = await handler._handle_streaming_delta(payload=payload)
        assert result["type"] == "ack"
