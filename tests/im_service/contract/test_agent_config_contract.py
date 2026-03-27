"""Contract tests for IM agent configuration endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import AgentProfileRepository, NodeRepository, UserRepository
from IM.ws.gateway_handler import GatewayHandler


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


def test_node_capabilities_contract_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose stable node capability fields for node-first agent creation (按需向网关拉取)."""

    async def _fake_node_capabilities(self, *, target_node_id: str, timeout_seconds: float = 15.0):  # noqa: ARG002
        return {
            "models": ["codex_oauth:gpt-5.4"],
            "skills": ["plan"],
            "tools": ["read"],
            "platform_default_model": None,
            "default_system_prompt": "",
        }

    monkeypatch.setattr(GatewayHandler, "request_node_capabilities", _fake_node_capabilities)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        response = client.get("/im/v1/nodes/node-1/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "node_id": "node-1",
        "skills": [{"name": "plan", "description": ""}],
        "tools": [{"name": "read", "description": ""}],
        "models": ["codex_oauth:gpt-5.4"],
        "platform_default_model": None,
        "default_system_prompt": "",
    }
