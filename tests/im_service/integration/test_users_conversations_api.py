"""Integration tests for users and conversations APIs."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def test_users_and_conversations_roundtrip(tmp_path: Path) -> None:
    """Create users then create/list conversation through HTTP endpoints."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_resp = client.post(
            "/im/v1/users",
            json={"username": "alice", "display_name": "Alice"},
        )
        bob_resp = client.post(
            "/im/v1/users",
            json={"username": "bob", "display_name": "Bob"},
        )

        assert alice_resp.status_code == 201
        assert bob_resp.status_code == 201

        users_resp = client.get("/im/v1/users")
        assert users_resp.status_code == 200
        users = users_resp.json()
        assert [item["username"] for item in users] == ["alice", "bob"]

        conversation_resp = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice & Bob",
                "participant_ids": [
                    alice_resp.json()["id"],
                    bob_resp.json()["id"],
                ],
            },
        )
        assert conversation_resp.status_code == 201
        conversation = conversation_resp.json()
        assert conversation["title"] == "Alice & Bob"
        assert len(conversation["participant_ids"]) == 2

        list_resp = client.get("/im/v1/conversations")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 1
        assert items[0]["id"] == conversation["id"]


def test_conversations_reject_unknown_participants(tmp_path: Path) -> None:
    """Return 400 when creating conversations with unknown participants."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        response = client.post(
            "/im/v1/conversations",
            json={
                "title": "invalid",
                "participant_ids": ["missing-user"],
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "participant_ids contains unknown users"
