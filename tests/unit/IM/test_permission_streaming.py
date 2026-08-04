"""Tests for permission_request / permission_resolved streaming_delta kinds.

bugfix-367: permission_request_json 列改为 list 形态(append-by-request_id),
EventBridge.on_permission_request 改用 append_permission_request,
on_permission_resolved 改用 update_permission_resolution。MessageResponse 暴露
permission_requests list 以让 REST 历史回放完整还原"按了多少次同意"。
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from IM.api.ws.event_types import EVENT_PERMISSION_REQUEST, EVENT_PERMISSION_RESOLVED
from IM.application.event_bridge import EventBridge
from IM.domain.models import Message
from IM.infra.db import initialize_schema as build_schema
from IM.infra.repositories.events import EventRepository
from IM.infra.repositories.messages import MessageRepository


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


def _insert_conversation(
    conn: sqlite3.Connection, cid: str, owner_id: str = "owner-1"
) -> None:
    conn.execute(
        "INSERT INTO conversations(id, title, owner_id, creator_id, is_pinned, is_muted, unread_count, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (cid, "chat", owner_id, "u1", 0, 0, 0, "2024-01-01T00:00:00"),
    )
    conn.commit()


def _insert_message(
    conn: sqlite3.Connection, msg_id: str, cid: str, sender_user_id: str
) -> None:
    conn.execute(
        "INSERT INTO messages(id, conversation_id, sender_user_id, sender_type, content, delivery_status, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (msg_id, cid, sender_user_id, "agent", "", "running", "2024-01-01T00:00:00"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# EventBridge — permission_request append (list semantics, bugfix-367)
# ---------------------------------------------------------------------------


class TestEventBridgePermissionRequest:
    """EventBridge.on_permission_request appends to list and emits WS event."""

    def _make_bridge(self, conn: sqlite3.Connection) -> tuple[EventBridge, list]:
        emitted: list = []

        def notify(event):
            emitted.append(event)

        msg_repo = MessageRepository(conn, notify=notify)
        evt_repo = EventRepository(conn, notify=notify)
        bridge = EventBridge(
            message_repository=msg_repo,
            event_repository=evt_repo,
        )
        return bridge, emitted

    def test_permission_requests_are_ordered_idempotent_and_resolved_by_id(
        self,
    ) -> None:
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, emitted = self._make_bridge(conn)
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={
                "request_id": "req-a",
                "tool_name": "bash",
                "question": "version 1",
            },
        )
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={
                "request_id": "req-a",
                "tool_name": "bash",
                "question": "version 2",
            },
        )
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={
                "request_id": "req-b",
                "tool_name": "write",
            },
        )
        bridge.on_permission_resolved(
            message_id="msg-1", request_id="req-b", decision="deny"
        )

        event_types = [
            json.loads(event.payload_json)["event_type"] for event in emitted
        ]
        assert EVENT_PERMISSION_REQUEST in event_types
        payload = json.loads(emitted[-1].payload_json)
        assert payload["event_type"] == EVENT_PERMISSION_RESOLVED
        assert payload["request_id"] == "req-b"
        assert payload["decision"] == "deny"

        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        persisted = json.loads(row["permission_request_json"])
        assert len(persisted) == 2
        assert persisted[0]["request_id"] == "req-a"
        assert persisted[0]["question"] == "version 2"
        assert persisted[0]["status"] == "pending"
        assert persisted[1]["request_id"] == "req-b"
        assert persisted[1]["status"] == "resolved"
        assert persisted[1]["decision"] == "deny"

    def test_on_permission_resolved_raises_when_request_id_missing(self) -> None:
        """resolve 未匹配到的 request_id 必须 raise, 防止 reducer 状态机被静默放空."""
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, _ = self._make_bridge(conn)
        with pytest.raises(ValueError, match="not found in permission_requests"):
            bridge.on_permission_resolved(
                message_id="msg-1", request_id="never-existed", decision="allow_once"
            )

    def test_on_permission_request_no_message_raises(self) -> None:
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")

        bridge, _ = self._make_bridge(conn)
        with pytest.raises(ValueError, match="message_id not found"):
            bridge.on_permission_request(
                message_id="nonexistent",
                permission_request={"request_id": "req-1", "tool_name": "bash"},
            )


# ---------------------------------------------------------------------------
# GatewayExecution — streaming_delta permission_request / permission_resolved kinds
# ---------------------------------------------------------------------------


class TestGatewayExecutionPermissionKinds:
    """GatewayExecution routes permission kinds to EventBridge."""

    def _make_handler_with_mock_bridge(self):
        from IM.ws.gateway.execution import GatewayExecution
        from IM.ws.gateway.sessions import GatewaySessions

        mock_bridge = MagicMock()
        execution = GatewayExecution(
            sessions=GatewaySessions(lock=asyncio.Lock()),
            event_bridge=mock_bridge,
            lock=asyncio.Lock(),
        )
        return execution, mock_bridge

    @pytest.mark.asyncio
    async def test_permission_streaming_kinds_reach_the_bridge(self) -> None:
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
        result = await handler.handle_streaming_delta(payload=payload)
        assert result["type"] == "ack"
        mock_bridge.on_permission_request.assert_called_once_with(
            message_id="msg-1",
            permission_request=payload["permission_request"],
        )
        resolved_payload = {
            "kind": "permission_resolved",
            "message_id": "msg-1",
            "request_id": "req-1",
            "decision": "deny",
        }
        resolved = await handler.handle_streaming_delta(payload=resolved_payload)

        assert resolved["type"] == "ack"
        mock_bridge.on_permission_resolved.assert_called_once_with(
            message_id="msg-1",
            request_id="req-1",
            decision="deny",
        )


# ---------------------------------------------------------------------------
# R2: REST endpoint POST /im/v1/conversations/{cid}/permissions/{request_id}
# ---------------------------------------------------------------------------


class TestPermissionRestEndpoint:
    """POST /im/v1/conversations/{cid}/permissions/{request_id} forwards to gateway WS."""

    def _make_app(self, tmp_path) -> tuple[object, dict]:
        from IM.app import create_app
        from IM.infra.db import connect, initialize_schema
        from IM.infra.repositories.agents import AgentProfileRepository
        from IM.infra.repositories.messages import MessageRepository
        from IM.infra.repositories.users import UserRepository
        from fastapi.testclient import TestClient

        db_path = tmp_path / "im.db"
        conn = connect(db_path)
        initialize_schema(conn)

        users = UserRepository(conn)
        agent_user = users.create_user(username="agent:beta", display_name="Beta")
        conn.close()

        app = create_app(db_path=db_path, upload_dir=tmp_path / "uploads")

        with TestClient(app) as client:
            reg = client.post(
                "/im/v1/auth/register",
                json={
                    "username": "alice",
                    "password": "pw12345678",
                    "display_name": "Alice",
                },
            )
            assert reg.status_code in (200, 201), f"register failed: {reg.text}"
            token = reg.json()["access_token"]
            owner_id = reg.json()["user"]["id"]

            conv_resp = client.post(
                "/im/v1/conversations",
                json={
                    "title": "Alice + Beta",
                    "participant_ids": [owner_id, agent_user.id],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert conv_resp.status_code in (200, 201), (
                f"create conv failed: {conv_resp.text}"
            )
            conv_id = conv_resp.json()["id"]

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

        return app, {
            "owner_id": owner_id,
            "conv_id": conv_id,
            "msg_id": msg.id,
            "agent_id": "beta",
            "token": token,
        }

    def test_submit_decision_forwards_permission_response_to_gateway(
        self, tmp_path
    ) -> None:
        from fastapi.testclient import TestClient

        app, ctx = self._make_app(tmp_path)

        with TestClient(app) as client:
            with patch.object(
                client.app.state.gateway_control,
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
        assert call_kwargs["reason"] is None

    def test_submit_deny_forwards_reason_to_gateway(self, tmp_path) -> None:
        """feat-440-M1: a deny with a user-supplied reason must pass it through to
        push_permission_response so it reaches PermissionResponse.reason."""
        from fastapi.testclient import TestClient

        app, ctx = self._make_app(tmp_path)

        with TestClient(app) as client:
            with patch.object(
                client.app.state.gateway_control,
                "push_permission_response",
                new=AsyncMock(return_value=True),
            ) as mock_push:
                resp = client.post(
                    f"/im/v1/conversations/{ctx['conv_id']}/permissions/req-1",
                    json={
                        "message_id": ctx["msg_id"],
                        "decision": "deny",
                        "reason": "  先别动这个文件  ",
                    },
                    headers={"Authorization": f"Bearer {ctx['token']}"},
                )

        assert resp.status_code == 200
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["decision"] == "deny"
        assert call_kwargs["reason"] == "先别动这个文件"

    def test_submit_deny_whitespace_only_reason_normalized_to_none(
        self, tmp_path
    ) -> None:
        """feat-440-M2 (F3): a non-frontend / direct-API caller can send a reason of
        pure whitespace ("   "). The backend must treat strip()-empty as "no reason"
        so it never reaches the LLM as a blank "the user said:\n   " — the gateway's
        ``reason or ""`` keeps a truthy whitespace string, so the strip must happen at
        the HTTP boundary."""
        from fastapi.testclient import TestClient

        app, ctx = self._make_app(tmp_path)

        with TestClient(app) as client:
            with patch.object(
                client.app.state.gateway_control,
                "push_permission_response",
                new=AsyncMock(return_value=True),
            ) as mock_push:
                resp = client.post(
                    f"/im/v1/conversations/{ctx['conv_id']}/permissions/req-1",
                    json={
                        "message_id": ctx["msg_id"],
                        "decision": "deny",
                        "reason": "   ",
                    },
                    headers={"Authorization": f"Bearer {ctx['token']}"},
                )

        assert resp.status_code == 200
        assert mock_push.call_args.kwargs["reason"] is None

    def test_submit_decision_not_found_conversation(self, tmp_path) -> None:
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
# bugfix-367: MessageResponse must expose permission_requests list so REST
# history reload can render all historical ask cards (not just the latest).
# ---------------------------------------------------------------------------


class TestMessageResponsePermissionRequests:
    """to_message_response() maps Message.permission_requests (list) to MessageResponse."""

    def _make_message(self, permission_requests=None) -> "Message":
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
            permission_requests=permission_requests or [],
        )

    def test_to_message_response_carries_all_entries_in_list(self) -> None:
        from IM.api.routes.messages import to_message_response

        msg = self._make_message(
            permission_requests=[
                {
                    "request_id": "req-1",
                    "tool_name": "bash",
                    "tool_input": {"command": "rm a"},
                    "question": "Allow bash?",
                    "options": [],
                    "status": "resolved",
                    "decision": "allow_once",
                },
                {
                    "request_id": "req-2",
                    "tool_name": "write",
                    "tool_input": {"file_path": "/tmp/x.py"},
                    "question": "Allow write?",
                    "options": [],
                    "status": "pending",
                },
            ]
        )
        response = to_message_response(msg)

        assert isinstance(response.permission_requests, list)
        assert len(response.permission_requests) == 2
        assert response.permission_requests[0]["request_id"] == "req-1"
        assert response.permission_requests[0]["status"] == "resolved"
        assert response.permission_requests[1]["request_id"] == "req-2"
        assert response.permission_requests[1]["status"] == "pending"
        assert to_message_response(self._make_message()).permission_requests == []
