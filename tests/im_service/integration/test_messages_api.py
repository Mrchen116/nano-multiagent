"""Integration tests for conversation messages APIs."""
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories import AgentProfileRepository, NodeRepository


def _create_user(client: TestClient, username: str) -> str:
    """Create a user and return its identifier."""
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_conversation(client: TestClient, user_id: str, title: str) -> str:
    """Create a conversation for a single participant."""
    response = client.post(
        "/im/v1/conversations",
        json={"title": title, "participant_ids": [user_id]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_messages_roundtrip_and_order(tmp_path: Path) -> None:
    """Create and list messages in insertion order for one conversation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, user_id, "chat")

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "content": "hello"},
        )
        second = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "content": "world"},
        )

        assert first.status_code == 201
        assert second.status_code == 201

        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages")
        assert listed.status_code == 200
        payload = listed.json()["items"]

        assert [item["content"] for item in payload] == ["hello", "world"]


def test_list_messages_mark_as_read_clears_conversation_unread_counter(tmp_path: Path) -> None:
    """Treat initial history load as read acknowledgement for unread badge sync."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, user_id, "chat")

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "content": "hello"},
        )
        second = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "content": "world"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        before_read = client.get(f"/im/v1/conversations/{conversation_id}")
        assert before_read.status_code == 200
        assert before_read.json()["unread_count"] == 2

        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages?mark_as_read=true")
        assert listed.status_code == 200
        assert [item["content"] for item in listed.json()["items"]] == ["hello", "world"]

        after_read = client.get(f"/im/v1/conversations/{conversation_id}")
        assert after_read.status_code == 200
        assert after_read.json()["unread_count"] == 0


def test_frontend_runtime_bundle_exposes_mark_as_read_flow(tmp_path: Path) -> None:
    """Ensure IM-hosted frontend bundle includes unread read-ack query flow used in real runtime."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        entry = client.get("/chat/5e82e46169d044d18662e5bc853065bb")
        assert entry.status_code == 200
        html = entry.text
        script_prefix = 'src="/assets/'
        script_index = html.find(script_prefix)
        assert script_index >= 0
        script_start = script_index + len('src="')
        script_end = html.find('"', script_start)
        assert script_end > script_start
        script_path = html[script_start:script_end]

        bundle = client.get(script_path)
        assert bundle.status_code == 200
        assert "mark_as_read" in bundle.text


def test_messages_are_isolated_by_conversation(tmp_path: Path) -> None:
    """Avoid leaking messages from one conversation to another."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        first_conversation = _create_conversation(client, user_id, "c1")
        second_conversation = _create_conversation(client, user_id, "c2")

        create_resp = client.post(
            f"/im/v1/conversations/{first_conversation}/messages",
            json={"sender_user_id": user_id, "content": "first-only"},
        )
        assert create_resp.status_code == 201

        second_list = client.get(f"/im/v1/conversations/{second_conversation}/messages")
        assert second_list.status_code == 200
        assert second_list.json()["items"] == []
        assert second_list.json()["next_before_message_id"] is None


def test_messages_support_sender_type_attachments_and_pagination(tmp_path: Path) -> None:
    """Expose rich message fields and cursor pagination for Web IM history."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, user_id, "chat")

        user_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "sender_type": "user", "content": "m1"},
        )
        agent_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={
                "sender_user_id": user_id,
                "sender_type": "agent",
                "content": "m2",
                "attachments": [
                    {
                        "url": "file:///tmp/result.txt",
                        "content_type": "text/plain",
                        "file_name": "result.txt",
                    }
                ],
            },
        )
        system_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "sender_type": "system", "content": "m3"},
        )

        assert user_message.status_code == 201
        assert agent_message.status_code == 201
        assert system_message.status_code == 201
        assert agent_message.json()["attachments"][0]["url"] == "file:///tmp/result.txt"

        first_page = client.get(f"/im/v1/conversations/{conversation_id}/messages?limit=2")
        assert first_page.status_code == 200
        first_items = first_page.json()["items"]
        assert [item["content"] for item in first_items] == ["m2", "m3"]
        assert first_page.json()["next_before_message_id"] == first_items[0]["id"]

        second_page = client.get(
            f"/im/v1/conversations/{conversation_id}/messages?limit=2&before_message_id={first_items[0]['id']}"
        )
        assert second_page.status_code == 200
        second_items = second_page.json()["items"]
        assert [item["content"] for item in second_items] == ["m1"]
        assert second_page.json()["next_before_message_id"] is None

        conversation = client.get(f"/im/v1/conversations/{conversation_id}")
        assert conversation.status_code == 200
        assert conversation.json()["unread_count"] == 3
        assert conversation.json()["last_message_at"] == system_message.json()["created_at"]


def test_user_stream_roundtrip_for_sent_message(tmp_path: Path) -> None:
    """用户 WebSocket 推送与消息写入一致的事件载荷。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        sender_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, sender_id, "chat")
        sent = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={
                "sender_user_id": sender_id,
                "sender_type": "agent",
                "content": "hello stream",
                "attachments": [{"url": "https://example.com/file.png", "content_type": "image/png"}],
            },
        )
        assert sent.status_code == 201
        with client.websocket_connect(f"/im/ws/user?user_id={sender_id}") as websocket:
            websocket.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
            seen: list[str] = []
            for _ in range(6):
                body = json.loads(websocket.receive_text())
                if body.get("op") == "event":
                    seen.append(json.dumps(body, ensure_ascii=True))
                if len(seen) >= 2:
                    break
            blob = " ".join(seen)
            assert "message.sent" in blob
            assert "message.delivered" in blob
            assert "conversation_id" in blob
            assert "agent" in blob
            assert "https://example.com/file.png" in blob


def test_sync_returns_global_event_cursor(tmp_path: Path) -> None:
    """/im/v1/sync 提供全局 max_event_id 供客户端对齐游标。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        sender_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, sender_id, "chat")

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": sender_id, "content": "old-1"},
        )
        second = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": sender_id, "content": "old-2"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        synced = client.get("/im/v1/sync")
        assert synced.status_code == 200
        max_event_id = synced.json()["max_event_id"]
        assert max_event_id >= 4


def test_messages_endpoint_includes_visible_relay_history_on_first_load(tmp_path: Path) -> None:
    """Return synthetic agent history rows so old conversations do not gain replies only after实时回放。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "owner")
        agent_a_user_id = _create_user(client, "agent:A")
        agent_q_user_id = _create_user(client, "agent:Q")
        create_group = client.post(
            "/im/v1/conversations",
            json={"title": "A + Q", "participant_ids": [owner_id, agent_a_user_id, agent_q_user_id]},
        )
        assert create_group.status_code == 201
        conversation_id = create_group.json()["id"]

        base_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner_id, "content": "大家下午去哪里了", "target_node_id": "node-offline"},
        )
        followup_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner_id, "content": "@agent:Q 还有你", "target_node_id": "node-offline"},
        )
        assert base_message.status_code == 503
        assert followup_message.status_code == 503

        connection = app.state.connection
        base_id = connection.execute(
            "SELECT id FROM messages WHERE conversation_id = ? ORDER BY rowid ASC LIMIT 1",
            (conversation_id,),
        ).fetchone()["id"]
        followup_id = connection.execute(
            "SELECT id FROM messages WHERE conversation_id = ? ORDER BY rowid DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()["id"]
        connection.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-03-26T00:00:00Z", base_id),
        )
        connection.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-03-26T00:00:03Z", followup_id),
        )
        connection.execute(
            """
            INSERT INTO conversation_events(conversation_id, message_id, event_type, delivery_status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                base_id,
                "relay.completed",
                "completed",
                '{"message_id":"' + base_id + '","relay_task_id":"relay-a-1","agent_id":"A","detail":"我不在现场，无法得知。你想让我帮你发消息问大家吗？"}',
                "2026-03-26T00:00:01Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_events(conversation_id, message_id, event_type, delivery_status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                base_id,
                "relay.completed",
                "completed",
                '{"message_id":"' + base_id + '","relay_task_id":"relay-q-1","agent_id":"Q","detail":"抱歉没明白，你是要我帮你问大家下午去哪儿了吗？"}',
                "2026-03-26T00:00:02Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_events(conversation_id, message_id, event_type, delivery_status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                followup_id,
                "relay.completed",
                "completed",
                '{"message_id":"' + followup_id + '","relay_task_id":"relay-a-2","agent_id":"A","detail":"我在这儿呢。你是指今天下午大家都去哪儿了吗？我这边没收到行程消息，要不要我帮你问一下？"}',
                "2026-03-26T00:00:04Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_events(conversation_id, message_id, event_type, delivery_status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                followup_id,
                "relay.completed",
                "completed",
                '{"message_id":"' + followup_id + '","relay_task_id":"relay-q-2","agent_id":"Q","detail":"在的。你想让我做什么？"}',
                "2026-03-26T00:00:05Z",
            ),
        )
        connection.commit()

        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert [item["content"] for item in items] == [
            "大家下午去哪里了",
            "我不在现场，无法得知。你想让我帮你发消息问大家吗？",
            "抱歉没明白，你是要我帮你问大家下午去哪儿了吗？",
            "@agent:Q 还有你",
            "我在这儿呢。你是指今天下午大家都去哪儿了吗？我这边没收到行程消息，要不要我帮你问一下？",
            "在的。你想让我做什么？",
        ]
        assert [item["id"] for item in items if item["sender_type"] == "agent"] == [
            f"{base_id}:relay:relay-a-1",
            f"{base_id}:relay:relay-q-1",
            f"{followup_id}:relay:relay-a-2",
            f"{followup_id}:relay:relay-q-2",
        ]
        assert [item["sender"]["id"] for item in items if item["sender_type"] == "agent"] == ["A", "Q", "A", "Q"]


def test_uploads_expose_im_hosted_paths_for_message_attachments(tmp_path: Path) -> None:
    """Accept raw file uploads and return IM-hosted URLs usable by Web IM messages."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, user_id, "chat")

        uploaded = client.post(
            "/im/v1/uploads?file_name=demo.txt",
            content=b"demo attachment body",
            headers={"Content-Type": "text/plain"},
        )

        assert uploaded.status_code == 201
        attachment = uploaded.json()
        assert attachment["file_name"] == "demo.txt"
        assert attachment["content_type"] == "text/plain"
        assert attachment["url"].startswith("http://testserver/im/uploads/")

        download = client.get(attachment["url"].removeprefix("http://testserver"))
        assert download.status_code == 200
        assert download.content == b"demo attachment body"

        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={
                "sender_user_id": user_id,
                "content": "",
                "attachments": [attachment],
            },
        )

        assert created.status_code == 201
        assert created.json()["content"] == ""
        assert created.json()["attachments"] == [attachment]


def test_direct_chat_reports_node_offline_when_relay_not_live_connected(tmp_path: Path) -> None:
    """Keep node board and direct-chat relay availability aligned on live connectivity."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "alice")
        agent_user_response = client.post(
            "/im/v1/users",
            json={"username": "agent:ops-bot", "display_name": "Ops Bot"},
        )
        assert agent_user_response.status_code == 201
        agent_user_id = agent_user_response.json()["id"]

        profile_repo = AgentProfileRepository(app.state.connection)
        profile_repo.upsert_profile(
            agent_id="ops-bot",
            owner_id=owner_id,
            display_name="Ops Bot",
            description="Ops helper",
            system_prompt="You are Ops Bot.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="MENTION",
            default_model=None,
            workspace_root="",
        )
        app.state.connection.execute("UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?", ("node-ops", "ops-bot"))
        app.state.connection.commit()

        node_repo = NodeRepository(app.state.connection)
        node_repo.upsert_node(node_id="node-ops", node_name="Ops Node", status="online", version="1.0.0")
        app.state.connection.execute(
            "UPDATE nodes SET last_heartbeat_at = ? WHERE node_id = ?",
            (datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "node-ops"),
        )
        app.state.connection.commit()

        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "You & Ops", "participant_ids": [owner_id, agent_user_id]},
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        nodes = client.get("/im/v1/nodes")
        assert nodes.status_code == 200
        node_row = next(item for item in nodes.json() if item["node_id"] == "node-ops")
        assert node_row["status"] == "offline"

        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": owner_id, "content": "ping ops"},
        )
        assert created.status_code == 503
        assert created.json()["detail"] == "target_node_id is not connected"
