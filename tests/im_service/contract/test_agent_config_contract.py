"""Contract tests for IM agent configuration endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.api.routes import agents as agent_routes
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
            workspace_root=None,
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
            "workspace_root",
            "workspace_is_default",
            "profile_version",
            "bound_nodes",
            "updated_at",
        }
        assert response.json()["workspace_root"].endswith("/nano-assistant/workspace/agent-1")
        assert response.json()["workspace_is_default"] is True

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


def test_agent_allowlist_options_contract_shape(tmp_path: Path, monkeypatch) -> None:
    """Expose stable selectable skill/tool/model option envelopes for settings UI."""
    monkeypatch.setattr(
        agent_routes,
        "_list_available_skill_options",
        lambda: [agent_routes.AllowlistOptionResponse(name="plan", description="Plan work")],
    )
    monkeypatch.setattr(
        agent_routes,
        "_list_available_tool_options",
        lambda: [agent_routes.AllowlistOptionResponse(name="read", description="Read files")],
    )
    monkeypatch.setattr(agent_routes, "_list_available_models", lambda: ["codexOAuth:gpt-5.2-codex", "claude-3-5-sonnet-20241022"])
    monkeypatch.setattr(agent_routes, "_platform_default_model", lambda: "codexOAuth:gpt-5.2-codex")

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        response = client.get("/im/v1/agents/allowlist-options")

    assert response.status_code == 200
    assert response.json() == {
        "skills": [{"name": "plan", "description": "Plan work"}],
        "tools": [{"name": "read", "description": "Read files"}],
        "model_options": ["codexOAuth:gpt-5.2-codex", "claude-3-5-sonnet-20241022"],
        "platform_default_model": "codexOAuth:gpt-5.2-codex",
        "default_system_prompt": agent_routes.PERSONAL_ASSISTANT_PROFILE.default_system_prompt,
    }
