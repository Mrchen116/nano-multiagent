"""Contract tests for creating IM agent profiles."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import NodeRepository, UserRepository


def test_agent_create_contract_shape_and_validation(tmp_path: Path) -> None:
    """Expose stable create response fields and reject unknown nodes."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        users = UserRepository(app.state.connection)
        owner = users.create_user(username="owner", display_name="Owner")
        NodeRepository(app.state.connection).upsert_node(node_id="node-1", node_name="MacBook")

        created = client.post(
            "/im/v1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "description": "first runtime agent",
                "system_prompt": "You are Alpha.",
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "MENTION",
                "default_model": "claude-sonnet-4",
                "node_id": "node-1",
            },
        )
        assert created.status_code == 201
        assert set(created.json()) == {
            "agent_id",
            "owner_id",
            "display_name",
            "description",
            "system_prompt",
            "skills",
            "tool_allowlist",
            "group_reply_policy",
            "default_model",
            "profile_version",
            "bound_nodes",
            "updated_at",
        }
        assert created.json()["bound_nodes"] == ["node-1"]
        assert isinstance(created.json()["updated_at"], str)
        assert created.json()["profile_version"] == 1

        duplicate = client.post(
            "/im/v1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha duplicate",
                "description": "duplicate",
                "system_prompt": "You are Alpha duplicate.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "default_model": None,
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "agent_id already exists"}

        missing_node = client.post(
            "/im/v1/agents",
            json={
                "agent_id": "agent-2",
                "owner_id": owner.owner_id,
                "display_name": "Beta",
                "description": "missing node",
                "system_prompt": "You are Beta.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "default_model": None,
                "node_id": "node-missing",
            },
        )
        assert missing_node.status_code == 404
        assert missing_node.json() == {"detail": "node_id not found"}
