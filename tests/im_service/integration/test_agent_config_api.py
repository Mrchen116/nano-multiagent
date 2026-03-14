"""Integration tests for IM agent configuration APIs."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import AgentProfileRepository, UserRepository


def test_agents_list_get_patch_and_conflict(tmp_path: Path) -> None:
    """List, read, and optimistically update agent configs through HTTP APIs."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        profiles = AgentProfileRepository(app.state.connection)
        seeded = profiles.upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            display_name="Alpha",
            description="initial",
            system_prompt="You are Alpha.",
            skills=["plan"],
            tool_allowlist=["read"],
            group_reply_policy="manual",
            default_model="gpt-4.1",
        )

        list_resp = client.get("/im/v1/agents")
        assert list_resp.status_code == 200
        assert list_resp.json() == [
            {
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "description": "initial",
                "profile_version": 1,
                "default_model": "gpt-4.1",
                "bound_nodes": [],
                "updated_at": list_resp.json()[0]["updated_at"],
            }
        ]

        get_resp = client.get(f"/im/v1/agents/{seeded.agent_id}/config")
        assert get_resp.status_code == 200
        assert get_resp.json()["profile_version"] == 1
        assert get_resp.json()["skills"] == ["plan"]

        patch_resp = client.patch(
            f"/im/v1/agents/{seeded.agent_id}/config",
            json={
                "profile_version": 1,
                "display_name": "Alpha v2",
                "description": "updated",
                "system_prompt": "You are Alpha v2.",
                "skills": ["plan", "review"],
                "tool_allowlist": ["read", "edit"],
                "group_reply_policy": "auto",
                "default_model": "claude-sonnet-4",
            },
        )
        assert patch_resp.status_code == 200
        body = patch_resp.json()
        assert body["display_name"] == "Alpha v2"
        assert body["profile_version"] == 2
        assert body["group_reply_policy"] == "auto"

        conflict_resp = client.patch(
            f"/im/v1/agents/{seeded.agent_id}/config",
            json={
                "profile_version": 1,
                "display_name": "stale",
                "description": "stale",
                "system_prompt": "stale",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
            },
        )
        assert conflict_resp.status_code == 409
        assert conflict_resp.json()["detail"] == "profile_version conflict"


def test_profile_updates_only_affect_new_conversations(tmp_path: Path) -> None:
    """Snapshot alias-backed direct conversations so old threads stay old and new threads pick up updates."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-1",
            owner_id=owner.owner_id,
            display_name="Alpha",
            description="initial",
            system_prompt="You are Alpha.",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="manual",
            default_model=None,
        )

        agent_participant = users.create_user(username="agent:agent-1", display_name="Alpha Alias")

        first_conv = client.post(
            "/im/v1/conversations",
            json={"title": "first", "participant_ids": [owner.id, agent_participant.id]},
        )
        assert first_conv.status_code == 201
        assert first_conv.json()["config_profile_version"] == 1

        patch_resp = client.patch(
            "/im/v1/agents/agent-1/config",
            json={
                "profile_version": 1,
                "display_name": "Alpha v2",
                "description": "updated",
                "system_prompt": "v2",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "manual",
                "default_model": None,
            },
        )
        assert patch_resp.status_code == 200

        second_conv = client.post(
            "/im/v1/conversations",
            json={"title": "second", "participant_ids": [owner.id, agent_participant.id]},
        )
        assert second_conv.status_code == 201

        first_conv_after_patch = client.get(f"/im/v1/conversations/{first_conv.json()['id']}")
        second_conv_after_patch = client.get(f"/im/v1/conversations/{second_conv.json()['id']}")
        assert first_conv_after_patch.status_code == 200
        assert second_conv_after_patch.status_code == 200
        assert first_conv.json()["config_profile_version"] == 1
        assert first_conv_after_patch.json()["config_profile_version"] == 1
        assert second_conv.json()["config_profile_version"] == 2
        assert second_conv_after_patch.json()["config_profile_version"] == 2
