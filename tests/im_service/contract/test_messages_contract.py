"""Contract tests for message delivery status fields."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.nodes import NodeRepository

from tests.im_service._auth_helpers import authorize, register_user


def _create_user(client: TestClient, username: str) -> str:
    """Register and authorize once; subsequent calls in the same test seed under tenant."""
    user = register_user(client, username=username)
    authorize(client, user)
    return user.id


def _create_conversation(client: TestClient, participant_id: str) -> str:
    response = client.post(
        "/im/v1/conversations",
        json={"type": "group", "title": "chat", "participant_ids": [participant_id]},
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
        assert payload["sender_type"] == "user"
        assert payload["attachments"] == []


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
        assert payload["items"] == [{"type": "message", "message": create_resp.json()}]
        assert payload["next_before_message_id"] is None


def test_message_contract_supports_sender_type_attachments_and_pagination(
    tmp_path: Path,
) -> None:
    """Expose rich message fields and pagination envelope in Web IM responses."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-contract", node_name="Contract", owner_id=alice_id
        )
        with client.websocket_connect("/im/ws/gateway") as gateway:
            gateway.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-contract",
                        "agents": ["contract-agent"],
                    },
                }
            )
            registration = gateway.receive_json()
            assert registration["type"] == "ack"
            conversation = client.post(
                "/im/v1/conversations",
                json={
                    "type": "direct",
                    "title": "Agent",
                    "participants": [{"type": "agent", "id": "contract-agent"}],
                },
            )
            assert conversation.status_code == 201, conversation.text
            conversation_id = conversation.json()["id"]
            created = client.post(
                f"/im/v1/conversations/{conversation_id}/messages?agent_id=contract-agent",
                headers={
                    "Authorization": f"Bearer {registration['payload']['gateway_access_token']}"
                },
                json={
                    "sender": {"type": "agent", "id": "contract-agent"},
                    "content": "hello",
                    "attachments": [
                        {
                            "url": "https://example.test/demo.txt",
                            "content_type": "text/plain",
                            "file_name": "demo.txt",
                        }
                    ],
                },
            )
            assert created.status_code == 201
            assert created.json()["sender_type"] == "agent"
            assert created.json()["attachments"][0]["file_name"] == "demo.txt"

            listed = client.get(
                f"/im/v1/conversations/{conversation_id}/messages?limit=1"
            )
            assert listed.status_code == 200
            payload = listed.json()
            assert list(payload.keys()) == ["items", "next_before_message_id"]
            assert payload["items"] == [{"type": "message", "message": created.json()}]
            assert payload["next_before_message_id"] == created.json()["id"]
