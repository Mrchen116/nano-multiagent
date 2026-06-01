"""Tests for permission_request / permission_resolved streaming_delta kinds.

bugfix-367: permission_request_json 列改为 list 形态(append-by-request_id),
EventBridge.on_permission_request 改用 append_permission_request,
on_permission_resolved 改用 update_permission_resolution。MessageResponse 暴露
permission_requests list 以让 REST 历史回放完整还原"按了多少次同意"。
"""

from __future__ import annotations

import json
import sqlite3
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

        msg_repo = MessageRepository(conn, notify=None)
        evt_repo = EventRepository(conn)
        bridge = EventBridge(
            message_repository=msg_repo,
            event_repository=evt_repo,
            notify=notify,
        )
        return bridge, emitted

    def test_on_permission_request_persists_as_list_with_one_entry(self) -> None:
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
                {
                    "id": "allow_once",
                    "label": "Allow once",
                    "description": "Allow this single action",
                },
                {"id": "deny", "label": "Deny", "description": "Block this action"},
            ],
        }
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request=permission_data,
        )

        assert len(emitted) == 1
        event = emitted[0]
        payload = json.loads(event.payload_json)
        assert payload["event_type"] == EVENT_PERMISSION_REQUEST
        assert payload["permission_request"]["request_id"] == "req-abc"
        assert payload["message_id"] == "msg-1"

        # bugfix-367: 持久化为 list 形态
        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        persisted = json.loads(row["permission_request_json"])
        assert isinstance(persisted, list)
        assert len(persisted) == 1
        assert persisted[0]["request_id"] == "req-abc"
        assert persisted[0]["status"] == "pending"

    def test_two_asks_on_same_message_accumulate_in_list(self) -> None:
        """bugfix-367 核心: 同一 message 上两次 ask 都保留, 不覆盖."""
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, emitted = self._make_bridge(conn)

        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={"request_id": "req-1", "tool_name": "bash"},
        )
        bridge.on_permission_resolved(
            message_id="msg-1", request_id="req-1", decision="allow_once"
        )
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={"request_id": "req-2", "tool_name": "write"},
        )

        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        persisted = json.loads(row["permission_request_json"])
        assert isinstance(persisted, list)
        assert len(persisted) == 2, "两次 ask 都必须保留, 不能覆盖"
        # 第一条 resolved, 第二条 pending —— 按时间顺序
        assert persisted[0]["request_id"] == "req-1"
        assert persisted[0]["status"] == "resolved"
        assert persisted[0]["decision"] == "allow_once"
        assert persisted[1]["request_id"] == "req-2"
        assert persisted[1]["status"] == "pending"

    def test_same_request_id_idempotent_replace(self) -> None:
        """同 request_id 重复 append 视为 idempotent 替换(网络重传等)."""
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, _ = self._make_bridge(conn)

        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={
                "request_id": "req-1",
                "tool_name": "bash",
                "question": "v1",
            },
        )
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={
                "request_id": "req-1",
                "tool_name": "bash",
                "question": "v2",
            },
        )

        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        persisted = json.loads(row["permission_request_json"])
        assert len(persisted) == 1
        assert persisted[0]["question"] == "v2"

    def test_on_permission_resolved_updates_only_target_entry(self) -> None:
        """update_permission_resolution 按 request_id 定位, 不动 list 中其他条目."""
        conn = _make_db()
        _insert_user(conn, "u1", "agent:alpha")
        _insert_conversation(conn, "conv-1")
        _insert_message(conn, "msg-1", "conv-1", "u1")

        bridge, emitted = self._make_bridge(conn)

        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={"request_id": "req-a", "tool_name": "bash"},
        )
        bridge.on_permission_request(
            message_id="msg-1",
            permission_request={"request_id": "req-b", "tool_name": "write"},
        )
        emitted.clear()

        bridge.on_permission_resolved(
            message_id="msg-1", request_id="req-b", decision="deny"
        )

        assert len(emitted) == 1
        payload = json.loads(emitted[0].payload_json)
        assert payload["event_type"] == EVENT_PERMISSION_RESOLVED
        assert payload["request_id"] == "req-b"
        assert payload["decision"] == "deny"

        row = conn.execute(
            "SELECT permission_request_json FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        persisted = json.loads(row["permission_request_json"])
        assert len(persisted) == 2
        assert persisted[0]["request_id"] == "req-a"
        assert persisted[0]["status"] == "pending", (
            "未指定 request_id 的条目状态不应被改"
        )
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
# gateway_handler — streaming_delta permission_request / permission_resolved kinds
# ---------------------------------------------------------------------------


class TestGatewayHandlerPermissionKinds:
    """gateway_handler._handle_streaming_delta routes new permission kinds to EventBridge."""

    def _make_handler_with_mock_bridge(self):
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
        """permission_response kind (IM→PA direction) is a no-op in GatewayHandler streaming delta."""
        handler, _ = self._make_handler_with_mock_bridge()

        payload = {
            "kind": "permission_response",
            "request_id": "req-1",
            "decision": "allow_once",
        }
        result = await handler._handle_streaming_delta(payload=payload)
        assert result["type"] == "ack"


# ---------------------------------------------------------------------------
# R2: REST endpoint POST /im/v1/conversations/{cid}/permissions/{request_id}
# ---------------------------------------------------------------------------


class TestPermissionRestEndpoint:
    """POST /im/v1/conversations/{cid}/permissions/{request_id} forwards to gateway WS."""

    def _make_app(self, tmp_path) -> tuple[object, dict]:
        from IM.app import create_app
        from IM.infra.db import connect, initialize_schema
        from IM.infra.repositories import (
            AgentProfileRepository,
            MessageRepository,
            UserRepository,
        )
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

    def test_to_message_response_empty_list_when_no_asks(self) -> None:
        from IM.api.routes.messages import to_message_response

        msg = self._make_message(permission_requests=[])
        response = to_message_response(msg)
        assert response.permission_requests == []
