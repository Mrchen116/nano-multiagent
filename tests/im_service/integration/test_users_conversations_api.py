"""Integration tests for conversation HTTP APIs (post feat-340-M1 multi-user auth).

The legacy ``/im/v1/users`` create/list endpoints were removed in R4; user creation
goes through ``/im/v1/auth/register``. These tests now assert the same conversation
behaviors via the auth-gated routes.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import make_app_client, register_user, authorize


def test_users_and_conversations_roundtrip(tmp_path: Path) -> None:
    """Single-tenant register + create/list a conversation through HTTP."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)

        conversation_resp = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice's room",
                "participant_ids": [alice.id],
            },
        )
        assert conversation_resp.status_code == 201, conversation_resp.text
        conversation = conversation_resp.json()
        assert conversation["title"] == "Alice's room"
        assert conversation["participant_ids"] == [alice.id]
        assert conversation["owner_id"] == alice.owner_id
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
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "before", "participant_ids": [alice.id]},
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
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        first = client.post(
            "/im/v1/conversations",
            json={"title": "first", "participant_ids": [alice.id]},
        ).json()
        second = client.post(
            "/im/v1/conversations",
            json={"title": "second", "participant_ids": [alice.id]},
        ).json()
        third = client.post(
            "/im/v1/conversations",
            json={"title": "third", "participant_ids": [alice.id]},
        ).json()

        pin_resp = client.patch(
            f"/im/v1/conversations/{first['id']}",
            json={"is_pinned": True},
        )
        assert pin_resp.status_code == 200

        create_message = client.post(
            f"/im/v1/conversations/{second['id']}/messages",
            json={"sender_user_id": alice.id, "content": "latest"},
        )
        assert create_message.status_code == 201

        items = client.get("/im/v1/conversations").json()["items"]
        assert [item["id"] for item in items] == [first["id"], second["id"], third["id"]]
        assert items[1]["last_message_preview"] == "latest"
        assert items[1]["last_message_at"] is not None
        assert items[1]["unread_count"] == 1


def test_conversations_reject_unknown_participants(tmp_path: Path) -> None:
    """Return 400 when creating conversations with unknown participants."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        response = client.post(
            "/im/v1/conversations",
            json={
                "title": "invalid",
                "participant_ids": ["missing-user"],
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "participant_ids contains unknown users"


def test_register_rejects_duplicate_username(tmp_path: Path) -> None:
    """Duplicate username on /im/v1/auth/register must return a client error, not 500."""
    with make_app_client(tmp_path) as client:
        first = client.post(
            "/im/v1/auth/register",
            json={"username": "peer", "password": "hunter2-strong", "display_name": "Teammate"},
        )
        duplicate = client.post(
            "/im/v1/auth/register",
            json={"username": "peer", "password": "hunter2-strong", "display_name": "OpsBot"},
        )

        assert first.status_code == 201
        assert duplicate.status_code == 409
