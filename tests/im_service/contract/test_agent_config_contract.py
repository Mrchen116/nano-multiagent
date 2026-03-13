"""Contract tests for IM agent configuration endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import AgentProfileRepository, UserRepository


def test_agent_config_contract_shape_and_conflict_status(tmp_path: Path) -> None:
    """Expose stable response fields and 409 conflict semantics for config PATCH."""
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
            skills=["plan"],
            tool_allowlist=["read"],
            group_reply_policy="manual",
            default_model=None,
        )

        response = client.get("/im/v1/agents/agent-1/config")
        assert response.status_code == 200
        assert set(response.json()) == {
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

        conflict = client.patch(
            "/im/v1/agents/agent-1/config",
            json={
                "profile_version": 2,
                "display_name": "Alpha",
                "description": "initial",
                "system_prompt": "You are Alpha.",
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "manual",
                "default_model": None,
            },
        )
        assert conflict.status_code == 409
        assert conflict.json() == {"detail": "profile_version conflict"}
