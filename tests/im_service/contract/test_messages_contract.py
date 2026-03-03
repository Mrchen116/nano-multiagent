"""Contract tests for message delivery status fields."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def _create_user(client: TestClient, username: str) -> str:
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_conversation(client: TestClient, participant_id: str) -> str:
    response = client.post(
        "/im/v1/conversations",
        json={"title": "chat", "participant_ids": [participant_id]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_message_contract_includes_delivery_status(tmp_path: Path) -> None:
    """Expose delivery status in create-message response body."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)

        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello"},
        )

        assert created.status_code == 201
        payload = created.json()
        assert payload["id"]
        assert payload["conversation_id"] == conversation_id
        assert payload["delivery_status"] == "completed"


def test_list_messages_contract_includes_delivery_status(tmp_path: Path) -> None:
    """Expose delivery status when listing messages for a conversation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        create_resp = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello"},
        )
        assert create_resp.status_code == 201

        listed = client.get(f"/im/v1/conversations/{conversation_id}/messages")

        assert listed.status_code == 200
        payload = listed.json()
        assert len(payload) == 1
        assert payload[0]["delivery_status"] == "completed"
