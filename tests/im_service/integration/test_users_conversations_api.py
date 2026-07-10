"""Integration tests for conversation HTTP APIs (post feat-340-M1 multi-user auth).

The legacy ``/im/v1/users`` create/list endpoints were removed in R4; user creation
goes through ``/im/v1/auth/register``. These tests now assert the same conversation
behaviors via the auth-gated routes.
"""

import json
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
        assert conversation["run_state"] == "idle"
        assert conversation["source_agent_id"] is None
        assert conversation["source_jsonl_path"] is None

        list_resp = client.get("/im/v1/conversations")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == conversation["id"]
        assert items[0]["run_state"] == "idle"

        detail_resp = client.get(f"/im/v1/conversations/{conversation['id']}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["id"] == conversation["id"]


def test_agent_conversation_response_includes_source_jsonl_path(
    tmp_path: Path,
) -> None:
    """Conversation API exposes the resolved kernel session JSONL when it exists."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)
        connection = client.app.state.connection
        workspace_root = tmp_path / "agent-1-workspace"
        connection.execute(
            """
            INSERT INTO users(id, username, display_name, owner_id, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            ("agent-user-1", "agent:agent-1", "Agent 1", alice.owner_id),
        )
        connection.execute(
            """
            INSERT INTO agent_profiles(
                agent_id, owner_id, node_id, display_name, description, system_prompt,
                skills_json, tool_allowlist_json, group_reply_policy, default_model,
                workspace_root, profile_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "agent-1",
                alice.owner_id,
                "node-1",
                "Agent 1",
                "",
                "You are Agent 1.",
                "[]",
                "[]",
                "manual",
                None,
                str(workspace_root),
                1,
            ),
        )
        connection.commit()

        conversation_resp = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice & Agent",
                "participant_ids": [alice.id, "agent-user-1"],
            },
        )
        assert conversation_resp.status_code == 201, conversation_resp.text
        conversation = conversation_resp.json()
        session_path = workspace_root / ".nanoassistant" / "sessions" / "sess-1.jsonl"
        session_path.parent.mkdir(parents=True)
        session_path.write_text(
            json.dumps(
                {
                    "type": "session_created",
                    "session_id": "sess-1",
                    "created_at": "2026-01-01T00:00:00Z",
                    "workspace_root": str(workspace_root),
                    "tool_allowlist": ["memory", "skill_view"],
                    "metadata": {
                        "workspace_config_dirname": ".nanoassistant",
                        "agent_id": "agent-1",
                        "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                        "conversation_id": conversation["id"],
                        "config_profile_version": 1,
                        "system_prompt": "You are Agent 1.",
                        "agent_features": {},
                        "conversation_type": "direct",
                        "self_evolution": {
                            "enabled": False,
                            "mode": "observe",
                        },
                        "title": "Agent 1",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        listed = client.get("/im/v1/conversations").json()["items"]
        synced = client.get("/im/v1/sync").json()["items"]

        assert listed[0]["source_agent_id"] == "agent-1"
        assert listed[0]["source_jsonl_path"] == str(session_path)
        assert synced[0]["source_agent_id"] == "agent-1"
        assert synced[0]["source_jsonl_path"] == str(session_path)


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
        assert [item["id"] for item in items] == [
            first["id"],
            second["id"],
            third["id"],
        ]
        assert items[1]["last_message_preview"] == "latest"
        assert items[1]["last_message_at"] is not None
        # alice is the conversation owner, so her own message does not increment unread_count.
        assert items[1]["unread_count"] == 0


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
            json={
                "username": "peer",
                "password": "hunter2-strong",
                "display_name": "Teammate",
            },
        )
        duplicate = client.post(
            "/im/v1/auth/register",
            json={
                "username": "peer",
                "password": "hunter2-strong",
                "display_name": "OpsBot",
            },
        )

        assert first.status_code == 201
        assert duplicate.status_code == 409
