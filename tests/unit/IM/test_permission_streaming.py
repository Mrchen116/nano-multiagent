"""Tests for permission_request / permission_resolved streaming_delta kinds.

bugfix-367: permission_request_json 列改为 list 形态(append-by-request_id),
EventBridge.on_permission_request 改用 append_permission_request,
on_permission_resolved 改用 update_permission_resolution。MessageResponse 暴露
permission_requests list 以让 REST 历史回放完整还原"按了多少次同意"。
"""

from __future__ import annotations

import json
import sqlite3

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
        "INSERT INTO conversations(id, title, owner_id, creator_id, created_at)"
        " VALUES (?,?,?,?,?)",
        (cid, "chat", owner_id, "u1", "2024-01-01T00:00:00"),
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
