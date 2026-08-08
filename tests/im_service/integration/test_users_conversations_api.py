"""Integration tests for conversation HTTP behaviors beyond the contract suite."""

from fastapi.testclient import TestClient
from pathlib import Path

from .conftest import make_app_client, register_user, authorize


def test_agent_conversation_projects_source_node_and_creates_gateway_prompt(
    tmp_path,
) -> None:
    """IM exposes no workspace path and only creates chat after Gateway prompt success."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)
        connection = client.app.state.connection
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
                agent_id, owner_id, node_id, display_name, description, custom_prompt,
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
                "/not-accessed-by-im",
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
        listed = client.get("/im/v1/conversations").json()["items"]
        synced = client.get("/im/v1/sync").json()["items"]

        assert listed[0]["source_agent_id"] == "agent-1"
        assert listed[0]["source_node_id"] == "node-1"
        assert "source_jsonl_path" not in listed[0]
        assert synced[0]["source_agent_id"] == "agent-1"
        assert synced[0]["source_node_id"] == "node-1"

        async def _gateway_prompt(**kwargs):
            assert kwargs["target_node_id"] == "node-1"
            assert kwargs["sources"] == [
                {
                    "conversation_id": conversation["id"],
                    "source_agent_id": "agent-1",
                }
            ]
            return {"prompt": "/skill:conversation-skill-distiller\nsource_jsonl_paths:\n  /gateway/session.jsonl"}

        client.app.state.gateway_control.request_distill_prompt = _gateway_prompt
        created = client.post(
            "/im/v1/conversations/distill-prompt",
            json={
                "sources": [
                    {
                        "conversation_id": conversation["id"],
                        "source_agent_id": "agent-1",
                    }
                ],
                "execution_agent_id": "agent-1",
                "target_scope": "agent",
            },
        )

        assert created.status_code == 201, created.text
        assert created.json()["prompt"].startswith("/skill:conversation-skill-distiller")
        direct = created.json()["conversation"]
        assert "target_node_id" not in direct
        pinned = connection.execute(
            "SELECT target_node_id FROM conversations WHERE id = ?", (direct["id"],)
        ).fetchone()
        assert pinned["target_node_id"] == "node-1"

        async def _unavailable_gateway_prompt(**_kwargs):
            return {"error_code": "source_unavailable", "message": "source session file is unavailable"}

        client.app.state.gateway_control.request_distill_prompt = _unavailable_gateway_prompt
        before = connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        unavailable = client.post(
            "/im/v1/conversations/distill-prompt",
            json={
                "sources": [
                    {
                        "conversation_id": conversation["id"],
                        "source_agent_id": "agent-1",
                    }
                ],
                "execution_agent_id": "agent-1",
                "target_scope": "agent",
            },
        )

        assert unavailable.status_code == 409
        assert unavailable.json()["detail"] == "source session file is unavailable"
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == before

        async def _blank_gateway_prompt(**_kwargs):
            return {"prompt": ""}

        client.app.state.gateway_control.request_distill_prompt = _blank_gateway_prompt
        blank = client.post(
            "/im/v1/conversations/distill-prompt",
            json={
                "sources": [
                    {
                        "conversation_id": conversation["id"],
                        "source_agent_id": "agent-1",
                    }
                ],
                "execution_agent_id": "agent-1",
                "target_scope": "agent",
            },
        )

        assert blank.status_code == 409
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == before


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
