"""Integration tests for end-to-end human chat API chain."""
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def _create_user(client: TestClient, username: str, display_name: str) -> str:
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": display_name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_human_chat_roundtrip_with_history_and_conversation_list(tmp_path: Path) -> None:
    """Cover create->send->history->conversations chain through HTTP API."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice", "Alice")
        bob_id = _create_user(client, "bob", "Bob")

        created_conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice & Bob",
                "participant_ids": [alice_id, bob_id],
            },
        )
        assert created_conversation.status_code == 201
        conversation_id = created_conversation.json()["id"]

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello"},
        )
        second = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": bob_id, "content": "hi"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        conversations_resp = client.get("/im/v1/conversations")
        assert conversations_resp.status_code == 200
        conversations = conversations_resp.json()["items"]
        assert any(item["id"] == conversation_id for item in conversations)

        messages_resp = client.get(f"/im/v1/conversations/{conversation_id}/messages")
        assert messages_resp.status_code == 200
        messages = messages_resp.json()["items"]
        assert [item["content"] for item in messages] == ["hello", "hi"]
        assert [item["delivery_status"] for item in messages] == ["completed", "completed"]

        conversation_detail = client.get(f"/im/v1/conversations/{conversation_id}")
        assert conversation_detail.status_code == 200
        assert conversation_detail.json()["unread_count"] == 2
        assert conversation_detail.json()["type"] == "direct"
