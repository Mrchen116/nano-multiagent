"""Integration tests for conversation messages APIs."""
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


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


def test_sse_events_roundtrip_for_sent_message(tmp_path: Path) -> None:
    """Emit SSE event stream entries that UI can consume for live rendering."""
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

        with client.stream(
            "GET",
            f"/im/v1/conversations/{conversation_id}/events?after_event_id=0&max_events=10&timeout_seconds=0.05",
        ) as stream_response:
            assert stream_response.status_code == 200
            body = "".join(chunk for chunk in stream_response.iter_text())

        assert "event: message.sent" in body
        assert "event: message.delivered" in body
        assert '"conversation_id"' in body
        assert '"sender_type":"agent"' in body
        assert '"attachments":[{"url":"https://example.com/file.png"' in body
