"""Integration tests for end-to-end human chat API chain."""
from pathlib import Path

from IM.repositories import UserRepository

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
        # Only bob's message counts as unread (alice is the conversation owner).
        assert conversation_detail.json()["unread_count"] == 1
        assert conversation_detail.json()["type"] == "direct"


def test_group_with_agent_appears_in_sidebar(tmp_path: Path) -> None:
    """POST group conversation containing an ownerless agent must appear in GET /im/v1/conversations.

    Regression for R3-1: when an agent participant has owner_id='', create_conversation
    previously assigned a random UUID as the conversation owner_id, so the caller
    could never find the conversation in their sidebar.
    """
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)

        # Create an agent user with no owner (ownerless, like an unbound agent)
        users = UserRepository(client.app.state.connection)
        agent_user = users.create_user(username="agent:bot", display_name="Bot")
        client.app.state.connection.execute(
            "UPDATE users SET owner_id = '' WHERE id = ?", (agent_user.id,)
        )
        client.app.state.connection.commit()

        create_resp = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice + Bot group",
                "participant_ids": [alice.id, agent_user.id],
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        conversation_id = create_resp.json()["id"]

        list_resp = client.get("/im/v1/conversations")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert any(item["id"] == conversation_id for item in items), (
            "Group conversation with ownerless agent must appear in caller's conversation list; "
            f"got ids: {[i['id'] for i in items]}"
        )


def test_cross_tenant_group_isolation(tmp_path: Path) -> None:
    """Owner B must not see conversations created by owner A.

    Regression guard: caller_owner_id fix must not break tenant isolation.
    """
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)

        create_resp = client.post(
            "/im/v1/conversations",
            json={"title": "Alice solo", "participant_ids": [alice.id]},
        )
        assert create_resp.status_code == 201, create_resp.text
        alice_conv_id = create_resp.json()["id"]

    # Bob registers in a separate app instance (separate tenant, separate db)
    with make_app_client(tmp_path, db_name="bob.db") as client_b:
        bob = register_user(client_b, username="bob", display_name="Bob")
        authorize(client_b, bob)

        list_resp = client_b.get("/im/v1/conversations")
        assert list_resp.status_code == 200
        bob_items = list_resp.json()["items"]
        assert not any(item["id"] == alice_conv_id for item in bob_items), (
            "Bob must not see Alice's conversation"
        )
