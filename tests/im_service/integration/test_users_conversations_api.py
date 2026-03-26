"""Integration tests for users and conversations APIs."""
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def _create_user(client: TestClient, username: str, display_name: str | None = None) -> dict[str, object]:
    """Create a user and return the response payload."""
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": display_name or username.title()},
    )
    assert response.status_code == 201
    return response.json()


def test_users_and_conversations_roundtrip(tmp_path: Path) -> None:
    """Create users then create/list conversation through HTTP endpoints."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice = _create_user(client, "alice", "Alice")
        bob = _create_user(client, "bob", "Bob")

        users_resp = client.get("/im/v1/users")
        assert users_resp.status_code == 200
        users = users_resp.json()
        assert [item["username"] for item in users] == ["alice", "bob"]

        conversation_resp = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice & Bob",
                "participant_ids": [alice["id"], bob["id"]],
            },
        )
        assert conversation_resp.status_code == 201
        conversation = conversation_resp.json()
        assert conversation["title"] == "Alice & Bob"
        assert len(conversation["participant_ids"]) == 2
        assert conversation["type"] == "direct"
        assert conversation["owner_id"]
        assert conversation["is_pinned"] is False
        assert conversation["is_muted"] is False
        assert conversation["unread_count"] == 0
        assert conversation["last_message_preview"] is None
        assert conversation["last_message_at"] is None

        list_resp = client.get("/im/v1/conversations")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == conversation["id"]

        detail_resp = client.get(f"/im/v1/conversations/{conversation['id']}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["id"] == conversation["id"]


def test_patch_conversation_updates_title_pin_and_mute(tmp_path: Path) -> None:
    """Allow Web IM to update mutable conversation metadata."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice = _create_user(client, "alice")
        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "before", "participant_ids": [alice["id"]]},
        ).json()

        updated_resp = client.patch(
            f"/im/v1/conversations/{conversation['id']}",
            json={"title": "after", "is_pinned": True, "is_muted": True},
        )

        assert updated_resp.status_code == 200
        updated = updated_resp.json()
        assert updated["title"] == "after"
        assert updated["is_pinned"] is True
        assert updated["is_muted"] is True


def test_conversation_list_orders_pinned_then_recent_activity(tmp_path: Path) -> None:
    """Keep pinned conversations first, then sort by recent message activity."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice = _create_user(client, "alice")
        first = client.post(
            "/im/v1/conversations",
            json={"title": "first", "participant_ids": [alice["id"]]},
        ).json()
        second = client.post(
            "/im/v1/conversations",
            json={"title": "second", "participant_ids": [alice["id"]]},
        ).json()
        third = client.post(
            "/im/v1/conversations",
            json={"title": "third", "participant_ids": [alice["id"]]},
        ).json()

        pin_resp = client.patch(
            f"/im/v1/conversations/{first['id']}",
            json={"is_pinned": True},
        )
        assert pin_resp.status_code == 200

        create_message = client.post(
            f"/im/v1/conversations/{second['id']}/messages",
            json={"sender_user_id": alice["id"], "content": "latest"},
        )
        assert create_message.status_code == 201

        items = client.get("/im/v1/conversations").json()["items"]
        assert [item["id"] for item in items] == [first["id"], second["id"], third["id"]]
        assert items[1]["last_message_preview"] == "latest"
        assert items[1]["last_message_at"] is not None
        assert items[1]["unread_count"] == 1


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


def test_users_reject_duplicate_username_without_500(tmp_path: Path) -> None:
    """Return a client error when the username already exists instead of bubbling a 500."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        first = client.post(
            "/im/v1/users",
            json={"username": "peer", "display_name": "Teammate"},
        )
        duplicate = client.post(
            "/im/v1/users",
            json={"username": "peer", "display_name": "OpsBot"},
        )
        users = client.get("/im/v1/users")

        assert first.status_code == 201
        assert duplicate.status_code == 400
        assert duplicate.json()["detail"] == "username already exists"
        assert users.status_code == 200
        assert [item["display_name"] for item in users.json()] == ["Teammate"]
