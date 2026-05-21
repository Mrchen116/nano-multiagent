"""Contract tests for IM agent configuration endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.repositories import AgentProfileRepository, NodeRepository, UserRepository
from IM.ws.gateway_handler import GatewayHandler

from tests.im_service._auth_helpers import authorize, register_user


def test_agent_config_contract_shape_and_conflict_status(tmp_path: Path) -> None:
    """Expose stable response fields and 409 conflict semantics for config PATCH."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
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
            "models": ["codex_oauth:gpt-5.5"],
            "skills": ["plan"],
            "tools": ["read"],
            "platform_default_model": None,
            "default_system_prompt": "",
        }

    monkeypatch.setattr(GatewayHandler, "request_node_capabilities", _fake_node_capabilities)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        response = client.get("/im/v1/nodes/node-1/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "node_id": "node-1",
        "skills": [{"name": "plan", "description": ""}],
        "tools": [{"name": "read", "description": ""}],
        "models": ["codex_oauth:gpt-5.5"],
        "platform_default_model": None,
        "default_system_prompt": "",
    }


def test_agent_capabilities_features_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent capabilities response must include features list forwarded from Gateway.

    feat-379-M2 (decision 7): IM forwards the FEATURE_REGISTRY projection
    from the Gateway verbatim; each item must carry the five required fields.
    """
    _GATEWAY_FEATURES = [
        {
            "key": "web_search",
            "label_i18n": "Web Search",
            "help_i18n": "Enable web search tool",
            "default_on": False,
            "available": True,
            "requires_tool": "web_search",
        },
        {
            "key": "memory",
            "label_i18n": "Memory",
            "help_i18n": "Enable long-term memory",
            "default_on": True,
            "available": False,
            "requires_tool": None,
        },
    ]

    async def _fake_agent_capabilities(
        self,  # noqa: ARG001
        *,
        target_node_id: str,  # noqa: ARG001
        agent_id: str,  # noqa: ARG001
        workspace_root: str,  # noqa: ARG001
        timeout_seconds: float = 5.0,  # noqa: ARG001
    ) -> dict[str, object]:
        return {
            "models": ["model-x"],
            "skills": [],
            "tools": [],
            "platform_default_model": None,
            "default_system_prompt": "",
            # feat-379-M2: features projection from FEATURE_REGISTRY
            "features": _GATEWAY_FEATURES,
        }

    monkeypatch.setattr(GatewayHandler, "request_agent_capabilities", _fake_agent_capabilities)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        profiles.upsert_profile(
            agent_id="agent-cap",
            owner_id=owner.owner_id,
            display_name="Cap Agent",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="always",
            default_model=None,
            workspace_root=None,
            node_id="node-1",
        )
        response = client.get("/im/v1/agents/agent-cap/capabilities")

    assert response.status_code == 200
    body = response.json()
    # capabilities response must include features key
    assert "features" in body
    features = body["features"]
    assert isinstance(features, list)
    assert len(features) == 2
    # each feature item must carry required fields
    required_feature_fields = {"key", "label_i18n", "help_i18n", "default_on", "available"}
    for feat in features:
        assert required_feature_fields.issubset(set(feat)), f"missing fields in {feat}"
    # spot-check first feature values round-tripped correctly
    assert features[0]["key"] == "web_search"
    assert features[0]["available"] is True
    assert features[1]["key"] == "memory"
    assert features[1]["available"] is False
    assert features[1]["requires_tool"] is None
