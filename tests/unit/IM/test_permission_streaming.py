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


# ---------------------------------------------------------------------------
# R2: REST endpoint POST /im/v1/conversations/{cid}/permissions/{request_id}
# ---------------------------------------------------------------------------


class TestPermissionRestEndpoint:
    """POST /im/v1/conversations/{cid}/permissions/{request_id} forwards to gateway WS."""

    def _make_app(self, tmp_path) -> tuple[object, dict]:
        """Create a minimal IM app with pre-seeded data for permission endpoint tests.

        Uses register + login via HTTP to get a valid JWT token so auth is
        exercised via the same path as production, not bypassed.
        """
        from IM.app import create_app
        from IM.infra.db import connect, initialize_schema
        from IM.infra.repositories import AgentProfileRepository, ConversationRepository, MessageRepository, UserRepository
        from fastapi.testclient import TestClient

        db_path = tmp_path / "im.db"
        conn = connect(db_path)
        initialize_schema(conn)

        # agent user pre-created directly (agents don't register via HTTP)
        users = UserRepository(conn)
        agent_user = users.create_user(username="agent:beta", display_name="Beta")
        conn.close()

        app = create_app(db_path=db_path, upload_dir=tmp_path / "uploads")

        with TestClient(app) as client:
            # Register and login as alice
            reg = client.post(
                "/im/v1/auth/register",
                json={"username": "alice", "password": "pw12345678", "display_name": "Alice"},
            )
            assert reg.status_code in (200, 201), f"register failed: {reg.text}"
            token = reg.json()["access_token"]
            owner_id = reg.json()["user"]["id"]

            # Create conversation
            conv_resp = client.post(
                "/im/v1/conversations",
                json={
                    "title": "Alice + Beta",
                    "participant_ids": [owner_id, agent_user.id],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert conv_resp.status_code in (200, 201), f"create conv failed: {conv_resp.text}"
            conv_id = conv_resp.json()["id"]

        # Re-open DB to insert agent profile + message
        conn2 = connect(db_path)
        profiles = AgentProfileRepository(conn2)
        profiles.upsert_profile(
            agent_id="beta",
            owner_id=owner_id,
            display_name="Beta",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
            node_id="node-x",
        )
        msgs = MessageRepository(conn2)
        msg = msgs.create_message(
            conversation_id=conv_id,
            sender_user_id=agent_user.id,
            content="",
            sender_type="agent",
            allow_empty=True,
            auto_complete_delivery=False,
        )
        conn2.close()

        return app, {"owner_id": owner_id, "conv_id": conv_id, "msg_id": msg.id, "agent_id": "beta", "token": token}

    def test_submit_decision_forwards_permission_response_to_gateway(self, tmp_path) -> None:
        """POST /im/v1/conversations/{cid}/permissions/{request_id} pushes to connected node."""
        from unittest.mock import AsyncMock
        from fastapi.testclient import TestClient

        app, ctx = self._make_app(tmp_path)

        with TestClient(app) as client:
            with patch.object(
                client.app.state.gateway_handler,
                "push_permission_response",
                new=AsyncMock(return_value=True),
            ) as mock_push:
                resp = client.post(
                    f"/im/v1/conversations/{ctx['conv_id']}/permissions/req-1",
                    json={"message_id": ctx["msg_id"], "decision": "allow_once"},
                    headers={"Authorization": f"Bearer {ctx['token']}"},
                )

        assert resp.status_code == 200
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["request_id"] == "req-1"
        assert call_kwargs["decision"] == "allow_once"
        assert call_kwargs["message_id"] == ctx["msg_id"]

    def test_submit_decision_not_found_conversation(self, tmp_path) -> None:
        """POST with nonexistent conversation_id returns 404."""
        from fastapi.testclient import TestClient

        app, ctx = self._make_app(tmp_path)

        with TestClient(app) as client:
            resp = client.post(
                "/im/v1/conversations/nonexistent/permissions/req-1",
                json={"message_id": ctx["msg_id"], "decision": "allow_once"},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# feat-333-M3/R3: MessageResponse must expose permission_request so REST
# history reload can restore pending permission cards after page refresh.
# ---------------------------------------------------------------------------


class TestMessageResponsePermissionRequest:
    """to_message_response() must map Message.permission_request to MessageResponse."""

    def _make_message(self, permission_request=None) -> "Message":
        """Create a minimal domain Message with optional permission_request."""
        from IM.domain.models import Message, Actor

        return Message(
            id="msg-perm-1",
            conversation_id="conv-1",
            sender=Actor(type="agent", id="agent-a", display_name="Alpha"),
            sender_user_id="u:agent-a",
            sender_type="agent",
            content="",
            attachments=[],
            delivery_status="running",
            created_at="2026-01-01T00:00:00",
            permission_request=permission_request,
        )

    def test_to_message_response_includes_permission_request_when_present(self) -> None:
        """MessageResponse must carry permission_request when the domain message has one."""
        from IM.api.routes.messages import to_message_response

        perm = {
            "request_id": "req-restore-1",
            "tool_name": "bash",
            "tool_input": {"command": "rm -rf /tmp"},
            "question": "Allow bash?",
            "options": [{"id": "allow_once", "label": "Allow once", "description": ""}],
            "status": "pending",
        }
        msg = self._make_message(permission_request=perm)
        response = to_message_response(msg)

        assert response.permission_request is not None, (
            "Expected permission_request to be present in MessageResponse — "
            "page refresh should restore pending permission cards from REST history"
        )
        assert response.permission_request["request_id"] == "req-restore-1"
        assert response.permission_request["status"] == "pending"

    def test_to_message_response_permission_request_is_none_when_absent(self) -> None:
        """MessageResponse.permission_request must be None when message has no pending request."""
        from IM.api.routes.messages import to_message_response

        msg = self._make_message(permission_request=None)
        response = to_message_response(msg)

        assert response.permission_request is None
