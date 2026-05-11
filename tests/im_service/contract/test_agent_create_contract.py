"""Contract tests for creating IM agent profiles."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import NodeRepository

from tests.im_service._auth_helpers import authorize, register_user


def test_agent_create_contract_shape_and_validation(tmp_path: Path) -> None:
    """Expose stable node-scoped create response fields and reject unknown/disconnected nodes."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(node_id="node-1", node_name="MacBook")

        async def fake_request_agent_create(*, target_node_id: str, payload: dict[str, object], timeout_seconds: float = 5.0):
            del timeout_seconds
            if target_node_id != "node-1":
                return None
            return {
                "agent_id": payload["agent_id"],
                "display_name": payload["display_name"],
                "description": payload["description"],
                "system_prompt": payload["system_prompt"],
                "skills": payload["skills"],
                "tool_allowlist": payload["tool_allowlist"],
                "group_reply_policy": payload["group_reply_policy"],
                "default_model": payload["default_model"],
                "workspace_root": "/srv/agents/agent-1",
            }

        app.state.gateway_handler.request_agent_create = fake_request_agent_create

        created = client.post(
            "/im/v1/nodes/node-1/agents",
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
            },
        )
        assert created.status_code == 201
        assert set(created.json()) == {
            "agent_id",
            "owner_id",
            "node_id",
            "display_name",
            "description",
            "system_prompt",
            "skills",
            "tool_allowlist",
            "group_reply_policy",
            "default_model",
            "workspace_root",
            "workspace_is_default",
            "profile_version",
            "updated_at",
        }
        assert created.json()["node_id"] == "node-1"
        assert created.json()["workspace_root"] == "/srv/agents/agent-1"
        assert created.json()["workspace_is_default"] is False
        assert isinstance(created.json()["updated_at"], str)
        assert created.json()["profile_version"] == 1

        duplicate = client.post(
            "/im/v1/nodes/node-1/agents",
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
            "/im/v1/nodes/node-missing/agents",
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
            },
        )
        # Post feat-340-M1: unknown node_id 404s at the owner-scope gate before
        # reaching the gateway dispatch.
        assert missing_node.status_code == 404
        assert missing_node.json() == {"detail": "node_id not found"}
