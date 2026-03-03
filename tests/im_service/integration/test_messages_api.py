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
        payload = listed.json()

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
        assert second_list.json() == []


def test_sse_events_roundtrip_for_sent_message(tmp_path: Path) -> None:
    """Emit SSE event stream entries that UI can consume for live rendering."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        sender_id = _create_user(client, "alice")
        receiver_id = _create_user(client, "bob")
        conversation_id = _create_conversation(client, sender_id, "chat")

        add_participant = client.post(
            "/im/v1/conversations",
            json={"title": "chat-2", "participant_ids": [sender_id, receiver_id]},
        )
        assert add_participant.status_code == 201
        conversation_id = add_participant.json()["id"]

        sent = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": sender_id, "content": "hello stream"},
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
        assert "\"conversation_id\"" in body
