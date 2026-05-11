"""Integration tests for end-to-end human chat API chain."""
from pathlib import Path

from .conftest import authorize, make_app_client, register_user, seed_user_under_owner


def test_human_chat_roundtrip_with_history_and_conversation_list(tmp_path: Path) -> None:
    """Cover create->send->history->conversations chain through HTTP API."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)
        bob_id = seed_user_under_owner(
            client, username="bob", display_name="Bob", owner_id=alice.owner_id
        )

        created_conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice & Bob",
                "participant_ids": [alice.id, bob_id],
            },
        )
        assert created_conversation.status_code == 201, created_conversation.text
        conversation_id = created_conversation.json()["id"]

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice.id, "content": "hello"},
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
