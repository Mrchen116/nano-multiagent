"""Integration tests for conversation HTTP behaviors beyond the contract suite."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from IM.ws.gateway.control import SessionLogResolution

from .conftest import make_app_client, register_user, authorize


def test_conversation_list_and_sync_resolve_session_log_through_target_gateway(
    tmp_path: Path,
) -> None:
    """IM treats the mirrored root as opaque and asks the owning Gateway for logs."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice", display_name="Alice")
        authorize(client, alice)
        connection = client.app.state.connection
        mirrored_remote_root = "/remote-gateway/agent-1-workspace"
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
                mirrored_remote_root,
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
        session_path = (
            "/remote-gateway/agent-1-workspace/.nanoassistant/sessions/sess-1.jsonl"
        )
        rpc_calls: list[dict[str, str]] = []

        async def fake_request_session_log_path(**kwargs):
            rpc_calls.append(kwargs)
            return SessionLogResolution(session_path, "ready")

        client.app.state.gateway_control.request_session_log_path = (
            fake_request_session_log_path
        )

        listed = client.get("/im/v1/conversations").json()["items"]
        synced = client.get("/im/v1/sync").json()["items"]

        assert listed[0]["source_agent_id"] == "agent-1"
        assert listed[0]["source_node_id"] == "node-1"
        assert listed[0]["source_jsonl_path"] == session_path
        assert listed[0]["source_jsonl_status"] == "ready"
        assert synced[0]["source_agent_id"] == "agent-1"
        assert synced[0]["source_node_id"] == "node-1"
        assert synced[0]["source_jsonl_path"] == session_path
        assert synced[0]["source_jsonl_status"] == "ready"
        assert rpc_calls == [
            {
                "target_node_id": "node-1",
                "agent_id": "agent-1",
                "conversation_id": conversation["id"],
            },
            {
                "target_node_id": "node-1",
                "agent_id": "agent-1",
                "conversation_id": conversation["id"],
            },
        ]


@pytest.mark.parametrize(
    "create_profile", [False, True], ids=["absent", "without-node"]
)
def test_conversation_source_without_routable_profile_is_temporarily_unavailable(
    tmp_path: Path, create_profile: bool
) -> None:
    """Keep an Agent-sourced transcript temporary when its node cannot be routed."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        connection = client.app.state.connection
        connection.execute(
            """
            INSERT INTO users(id, username, display_name, owner_id, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            ("agent-user-1", "agent:agent-1", "Agent 1", alice.owner_id),
        )
        if create_profile:
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
                    None,
                    "Agent 1",
                    "",
                    "You are Agent 1.",
                    "[]",
                    "[]",
                    "manual",
                    None,
                    "/remote-gateway/agent-1-workspace",
                    1,
                ),
            )
        connection.commit()
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Alice & Agent",
                "participant_ids": [alice.id, "agent-user-1"],
            },
        )
        assert conversation.status_code == 201, conversation.text

        async def unexpected_resolution(**_kwargs):
            raise AssertionError(
                "an unroutable Agent must not invoke Gateway resolution"
            )

        client.app.state.gateway_control.request_session_log_path = (
            unexpected_resolution
        )
        listed = client.get("/im/v1/conversations").json()["items"]
        synced = client.get("/im/v1/sync").json()["items"]

    for response in (listed[0], synced[0]):
        assert response["source_agent_id"] == "agent-1"
        assert response["source_node_id"] is None
        assert response["source_jsonl_path"] is None
        assert response["source_jsonl_status"] == "unavailable"


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
