"""Integration tests for conversation messages APIs."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from IM.infra.repositories.users import UserRepository

from .conftest import authorize, make_app_client, register_user, seed_user_under_owner


def _create_user(client: TestClient, username: str) -> str:
    """Create a user for the IM tests, transparently handling multi-tenant auth.

    First call → registers a fresh tenant and authorizes the client.
    Subsequent calls → seed additional participant users sharing the first caller's
    tenant (so conversations involving multiple users are all owned by the caller).
    The behavior keeps legacy test code working without rewriting each test, while
    still going through the new auth gate on the actual route layer.
    """
    auth_header = client.headers.get("Authorization")
    if auth_header is None:
        user = register_user(client, username=username)
        authorize(client, user)
        return user.id
    # Reuse the existing tenant's owner_id by reading /im/v1/me
    me = client.get("/im/v1/me").json()
    return seed_user_under_owner(client, username=username, owner_id=me["owner_id"])


def _create_conversation(client: TestClient, user_id: str, title: str) -> str:
    """Create a conversation for a single participant."""
    response = client.post(
        "/im/v1/conversations",
        json={"title": title, "participant_ids": [user_id]},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _message_items(timeline_items: list[dict]) -> list[dict]:
    """Extract normal messages from a typed conversation timeline response."""
    return [item["message"] for item in timeline_items if item["type"] == "message"]


def test_external_find_or_create_and_message_display_name_roundtrip(
    tmp_path: Path,
) -> None:
    """Expose the shadow conversation entrypoint and sender display name over HTTP."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "owner")
        agent_user_id = _create_user(client, "agent:plato")
        profile_repo = AgentProfileRepository(app.state.connection)
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        profile_repo.upsert_profile(
            agent_id="plato",
            owner_id=owner.owner_id,
            display_name="Plato",
            description="",
            system_prompt="You are Plato.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="MENTION",
            default_model=None,
            workspace_root="",
        )

        created = client.post(
            "/im/v1/conversations/external/find-or-create",
            json={
                "external_source": "feishu",
                "external_chat_id": "ou_user",
                "agent_id": "plato",
                "title": "Plato · feishu",
                "is_group": False,
                "participant_ids": [f"user:{owner_id}", "agent:plato"],
                "metadata": {"channel": "feishu"},
            },
        )
        assert created.status_code == 201, created.text
        conversation = created.json()
        assert conversation["type"] == "direct"
        assert conversation["external_source"] == "feishu"
        assert conversation["external_chat_id"] == "ou_user"
        assert conversation["config_agent_id"] == "plato"

        same = client.post(
            "/im/v1/conversations/external/find-or-create",
            json={
                "external_source": "feishu",
                "external_chat_id": "ou_user",
                "agent_id": "plato",
                "title": "Plato renamed · feishu",
                "is_group": False,
                "participant_ids": [f"user:{owner_id}", f"user:{agent_user_id}"],
                "metadata": {},
            },
        )
        assert same.status_code == 200, same.text
        assert same.json()["id"] == conversation["id"]
        assert same.json()["title"] == "Plato renamed · feishu"

        message = client.post(
            f"/im/v1/conversations/{conversation['id']}/messages",
            json={
                "sender_user_id": owner_id,
                "content": "from feishu",
                "sender_display_name": "你",
                "attachments": [
                    {
                        "url": "https://example.test/a.png",
                        "content_type": "image/png",
                        "file_name": "a.png",
                    }
                ],
                "suppress_relay": True,
            },
        )
        assert message.status_code == 201, message.text
        assert message.json()["sender"]["display_name"] == "你"
        rows = app.state.connection.execute(
            """
            SELECT event_type, payload_json
            FROM conversation_events
            WHERE conversation_id = ? AND message_id = ?
            ORDER BY event_id
            """,
            (conversation["id"], message.json()["id"]),
        ).fetchall()
        assert [row["event_type"] for row in rows] == [
            "message.sent",
            "message.created",
            "message.delivered",
        ]
        sent_payload = json.loads(rows[0]["payload_json"])
        created_payload = json.loads(rows[1]["payload_json"])
        delivered_payload = json.loads(rows[2]["payload_json"])
        assert sent_payload["semantic"] == "persisted_to_im"
        assert delivered_payload["semantic"] == "message_history_ready"
        assert created_payload["content"] == "from feishu"
        assert created_payload["attachments"] == [
            {
                "url": "https://example.test/a.png",
                "content_type": "image/png",
                "file_name": "a.png",
            }
        ]
        assert created_payload["sender"]["display_name"] == "你"
        assert created_payload["sender_display_name"] == "你"


def test_list_messages_mark_as_read_clears_conversation_unread_counter(
    tmp_path: Path,
) -> None:
    """Treat initial history load as read acknowledgement for unread badge sync."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        # bob sends both messages so they count as unread (owner's own messages are excluded).
        bob_id = _create_user(client, "bob")
        # Include bob in the conversation so his messages pass participant validation.
        resp = client.post(
            "/im/v1/conversations",
            json={"title": "chat", "participant_ids": [user_id, bob_id]},
        )
        assert resp.status_code == 201, resp.text
        conversation_id = resp.json()["id"]

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": bob_id, "content": "hello"},
        )
        second = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": bob_id, "content": "world"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        before_read = client.get(f"/im/v1/conversations/{conversation_id}")
        assert before_read.status_code == 200
        assert before_read.json()["unread_count"] == 2

        listed = client.get(
            f"/im/v1/conversations/{conversation_id}/messages?mark_as_read=true"
        )
        assert listed.status_code == 200
        assert [item["content"] for item in _message_items(listed.json()["items"])] == [
            "hello",
            "world",
        ]

        after_read = client.get(f"/im/v1/conversations/{conversation_id}")
        assert after_read.status_code == 200
        assert after_read.json()["unread_count"] == 0


def test_timeline_pagination_keeps_boundary_with_anchor_without_spending_limit(
    tmp_path: Path,
) -> None:
    """A boundary follows its anchor's message cursor rather than becoming a page item."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "alice")
        owner = UserRepository(app.state.connection).get_user(user_id=owner_id)
        assert owner is not None
        agent_user_id = seed_user_under_owner(
            client,
            username="agent:planner",
            owner_id=owner.owner_id,
        )
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Planner",
                "participant_ids": [owner_id, agent_user_id],
            },
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["id"]
        posted = [
            client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                json={"sender_user_id": owner_id, "content": content},
            )
            for content in ("m1", "m2", "m3")
        ]
        assert all(response.status_code == 201 for response in posted)
        anchor_id = posted[-1].json()["id"]

        with client.websocket_connect("/im/ws/gateway") as gateway:
            gateway.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": ["planner"]},
                }
            )
            assert gateway.receive_json()["type"] == "ack"
            gateway.send_json(
                {
                    "type": "agent.config.boundary",
                    "payload": {
                        "boundary_id": "before-m3",
                        "node_id": "node-1",
                        "conversation_id": conversation_id,
                        "agent_id": "planner",
                        "before_message_id": anchor_id,
                        "runtime_fingerprint": "runtime-3",
                        "fingerprint_schema": "v1",
                        "profile_version": 3,
                        "applied_at": "2026-07-21T00:00:00Z",
                    },
                }
            )
            assert gateway.receive_json()["type"] == "ack"

        newest_page = client.get(
            f"/im/v1/conversations/{conversation_id}/messages?limit=1"
        )
        assert newest_page.status_code == 200, newest_page.text
        assert [item["type"] for item in newest_page.json()["items"]] == [
            "agent_config_changed",
            "message",
        ]
        newest_messages = _message_items(newest_page.json()["items"])
        assert [item["content"] for item in newest_messages] == ["m3"]
        assert newest_page.json()["next_before_message_id"] == anchor_id

        older_page = client.get(
            f"/im/v1/conversations/{conversation_id}/messages?limit=1&before_message_id={anchor_id}"
        )
        assert older_page.status_code == 200, older_page.text
        assert [item["type"] for item in older_page.json()["items"]] == ["message"]
        older_messages = _message_items(older_page.json()["items"])
        assert [item["content"] for item in older_messages] == ["m2"]
        assert older_page.json()["next_before_message_id"] == older_messages[0]["id"]


def test_messages_endpoint_includes_visible_relay_history_on_first_load(
    tmp_path: Path,
) -> None:
    """Return synthetic agent history rows so old conversations do not gain replies only after实时回放。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "owner")
        agent_a_user_id = _create_user(client, "agent:A")
        agent_q_user_id = _create_user(client, "agent:Q")
        create_group = client.post(
            "/im/v1/conversations",
            json={
                "title": "A + Q",
                "participant_ids": [owner_id, agent_a_user_id, agent_q_user_id],
            },
        )
        assert create_group.status_code == 201
        conversation_id = create_group.json()["id"]

        base_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={
                "sender_user_id": owner_id,
                "content": "大家下午去哪里了",
                "target_node_id": "node-offline",
            },
        )
        followup_message = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={
                "sender_user_id": owner_id,
                "content": "@agent:Q 还有你",
                "target_node_id": "node-offline",
            },
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
                '{"message_id":"'
                + base_id
                + '","relay_task_id":"relay-a-1","agent_id":"A","detail":"我不在现场，无法得知。你想让我帮你发消息问大家吗？"}',
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
                '{"message_id":"'
                + base_id
                + '","relay_task_id":"relay-q-1","agent_id":"Q","detail":"抱歉没明白，你是要我帮你问大家下午去哪儿了吗？"}',
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
                '{"message_id":"'
                + followup_id
                + '","relay_task_id":"relay-a-2","agent_id":"A","detail":"我在这儿呢。你是指今天下午大家都去哪儿了吗？我这边没收到行程消息，要不要我帮你问一下？"}',
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
                '{"message_id":"'
                + followup_id
                + '","relay_task_id":"relay-q-2","agent_id":"Q","detail":"在的。你想让我做什么？"}',
                "2026-03-26T00:00:05Z",
            ),
        )
        connection.commit()

        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages")
        assert listed.status_code == 200
        items = _message_items(listed.json()["items"])
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
        assert [
            item["sender"]["id"] for item in items if item["sender_type"] == "agent"
        ] == ["A", "Q", "A", "Q"]


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


def test_direct_chat_reports_node_offline_when_relay_not_live_connected(
    tmp_path: Path,
) -> None:
    """Keep node board and direct-chat relay availability aligned on live connectivity."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner_id = _create_user(client, "alice")
        agent_user_id = _create_user(client, "agent:ops-bot")

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
        app.state.connection.execute(
            "UPDATE agent_profiles SET node_id = ? WHERE agent_id = ?",
            ("node-ops", "ops-bot"),
        )
        app.state.connection.commit()

        node_repo = NodeRepository(app.state.connection)
        node_repo.upsert_node(
            node_id="node-ops", node_name="Ops Node", status="online", version="1.0.0"
        )
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


def test_upload_rejects_disallowed_mime_type(tmp_path: Path) -> None:
    """Block uploads outside the MIME white-list to keep agent intake bounded (M8 decision 8)."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        _create_user(client, "alice")

        response = client.post(
            "/im/v1/uploads?file_name=evil.sh",
            content=b"#!/bin/sh\necho hi\n",
            headers={"Content-Type": "application/x-sh"},
        )
        assert response.status_code == 415
        assert "unsupported" in response.json()["detail"].lower()


def test_upload_accepts_whitelisted_text_markdown(tmp_path: Path) -> None:
    """Accept all white-listed text and document types (text/markdown is in white-list)."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        _create_user(client, "alice")

        response = client.post(
            "/im/v1/uploads?file_name=notes.md",
            content=b"# notes\n",
            headers={"Content-Type": "text/markdown"},
        )
        assert response.status_code == 201
        assert response.json()["content_type"] == "text/markdown"


def test_upload_rejects_body_above_size_limit(tmp_path: Path) -> None:
    """Reject upload bodies above the 10 MB per-file ceiling (M8 decision 8)."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        _create_user(client, "alice")

        oversized = b"x" * (10 * 1024 * 1024 + 1)
        response = client.post(
            "/im/v1/uploads?file_name=big.txt",
            content=oversized,
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 413


def test_create_message_rejects_more_than_five_attachments(tmp_path: Path) -> None:
    """Cap one message at 5 attachments to keep agent intake bounded (M8 decision 8)."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        user_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, user_id, "chat")

        too_many = [
            {
                "url": f"http://testserver/im/uploads/{i}.txt",
                "content_type": "text/plain",
                "file_name": f"{i}.txt",
            }
            for i in range(6)
        ]
        response = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": user_id, "content": "", "attachments": too_many},
        )
        assert response.status_code == 400
        assert "attachments" in response.json()["detail"].lower()


def test_caller_idempotency_key_is_scoped_to_conversation_and_owner(
    tmp_path: Path,
) -> None:
    """A caller retry key must not disclose or suppress another conversation's message."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as owner_client, TestClient(app) as other_owner_client:
        owner = register_user(owner_client, username="idempotency-owner")
        authorize(owner_client, owner)
        first_conversation = _create_conversation(owner_client, owner.id, "first")
        second_conversation = _create_conversation(owner_client, owner.id, "second")
        other_owner = register_user(other_owner_client, username="idempotency-other")
        authorize(other_owner_client, other_owner)
        other_conversation = _create_conversation(
            other_owner_client, other_owner.id, "other"
        )

        first = owner_client.post(
            f"/im/v1/conversations/{first_conversation}/messages",
            json={"sender_user_id": owner.id, "content": "first"},
            headers={"Idempotency-Key": "shared-retry-key"},
        )
        same_retry = owner_client.post(
            f"/im/v1/conversations/{first_conversation}/messages",
            json={"sender_user_id": owner.id, "content": "first retry"},
            headers={"Idempotency-Key": "shared-retry-key"},
        )
        second = owner_client.post(
            f"/im/v1/conversations/{second_conversation}/messages",
            json={"sender_user_id": owner.id, "content": "second"},
            headers={"Idempotency-Key": "shared-retry-key"},
        )
        other = other_owner_client.post(
            f"/im/v1/conversations/{other_conversation}/messages",
            json={"sender_user_id": other_owner.id, "content": "other"},
            headers={"Idempotency-Key": "shared-retry-key"},
        )

        assert first.status_code == 201, first.text
        assert same_retry.status_code == 201, same_retry.text
        assert same_retry.json()["id"] == first.json()["id"]
        assert second.status_code == 201, second.text
        assert second.json()["id"] != first.json()["id"]
        assert other.status_code == 201, other.text
        assert other.json()["id"] not in {first.json()["id"], second.json()["id"]}
