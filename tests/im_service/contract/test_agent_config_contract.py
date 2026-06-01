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
        # feat-379-M5: features + custom_prompt must now appear in config response
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
            "features",
            "custom_prompt",
        }
        assert response.json()["workspace_root"].endswith(
            "/nano-assistant/workspace/agent-1"
        )
        assert response.json()["workspace_is_default"] is True


def test_patch_agent_config_persists_features_and_custom_prompt(tmp_path: Path) -> None:
    """PATCH /im/v1/agents/{id}/config must accept and persist features + custom_prompt.

    feat-379-M5 (ISSUE-2): the route was previously ignoring these two fields;
    GET after PATCH must reflect the written values.
    """
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner2", display_name="Owner2")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        profiles.upsert_profile(
            agent_id="agent-persist",
            owner_id=owner.owner_id,
            display_name="Persist Agent",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=["memory"],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
        )

        # PATCH with features + custom_prompt
        patch_resp = client.patch(
            "/im/v1/agents/agent-persist/config",
            json={
                "profile_version": 1,
                "display_name": "Persist Agent",
                "description": "",
                "system_prompt": "",
                "skills": [],
                "tool_allowlist": ["memory"],
                "group_reply_policy": "manual",
                "default_model": None,
                "features": {"memory_curation": False},
                "custom_prompt": "You are a helpful chef.",
            },
        )
        assert patch_resp.status_code == 200, patch_resp.text
        body = patch_resp.json()
        # Response must echo back the written features + custom_prompt
        assert body["features"] == {"memory_curation": False}, (
            f"features not persisted: {body}"
        )
        assert body["custom_prompt"] == "You are a helpful chef.", (
            f"custom_prompt not persisted: {body}"
        )

        # GET must return the same values (proves DB write, not just response echo)
        get_resp = client.get("/im/v1/agents/agent-persist/config?source=mirror")
        assert get_resp.status_code == 200
        get_body = get_resp.json()
        assert get_body["features"] == {"memory_curation": False}
        assert get_body["custom_prompt"] == "You are a helpful chef."


def test_node_capabilities_contract_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expose stable node capability fields for node-first agent creation (按需向网关拉取)."""

    async def _fake_node_capabilities(
        self, *, target_node_id: str, timeout_seconds: float = 15.0
    ):  # noqa: ARG002
        return {
            "models": ["codex_oauth:gpt-5.5"],
            "skills": ["plan"],
            "tools": ["read"],
            "platform_default_model": None,
            "default_system_prompt": "",
        }

    monkeypatch.setattr(
        GatewayHandler, "request_node_capabilities", _fake_node_capabilities
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        response = client.get("/im/v1/nodes/node-1/capabilities")

    assert response.status_code == 200
    body = response.json()
    # feat-379-M6 (ISSUE-1): features list added; other fields unchanged
    assert body["node_id"] == "node-1"
    assert body["skills"] == [{"name": "plan", "description": ""}]
    assert body["tools"] == [{"name": "read", "description": ""}]
    assert body["models"] == ["codex_oauth:gpt-5.5"]
    assert body["platform_default_model"] is None
    assert body["default_system_prompt"] == ""
    assert "features" in body
    # Gateway payload has no features field → IM returns empty list (graceful degradation)
    assert body["features"] == []


# feat-379-M6 (ISSUE-1): node capabilities must expose features list so create page
# can render the Features toggles without a per-agent capabilities call.
def test_node_capabilities_includes_features_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/nodes/{id}/capabilities must include a features list from Gateway.

    The agent-create page calls getNodeCapabilities (not getAgentCapabilities) because
    the agent doesn't exist yet.  Without features in the node capabilities response
    the frontend capabilityFeatures array is empty and the Features section is hidden.
    """

    async def _fake_node_capabilities_with_features(
        self, *, target_node_id: str, timeout_seconds: float = 15.0
    ):  # noqa: ARG002
        return {
            "models": ["gpt-4"],
            "skills": [],
            "tools": [],
            "platform_default_model": None,
            "default_system_prompt": "",
            "features": [
                {
                    "key": "memory_curation",
                    "label_i18n": "agents.features.memoryCuration.label",
                    "help_i18n": "agents.features.memoryCuration.help",
                    "default_on": True,
                    "available": True,
                    "requires_tool": "memory",
                }
            ],
        }

    monkeypatch.setattr(
        GatewayHandler,
        "request_node_capabilities",
        _fake_node_capabilities_with_features,
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        response = client.get("/im/v1/nodes/node-1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert "features" in body, (
        "node capabilities must contain a features list (ISSUE-1 regression)"
    )
    assert isinstance(body["features"], list)
    assert len(body["features"]) >= 1
    feat = body["features"][0]
    assert feat["key"] == "memory_curation"
    assert feat["default_on"] is True


# ---------------------------------------------------------------------------
# feat-379-M7 ISSUE-2: live-merge must not clobber features/custom_prompt
# ---------------------------------------------------------------------------


def test_get_agent_config_live_merge_preserves_features_and_custom_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /im/v1/agents/{id}/config?source=live must not overwrite features/custom_prompt.

    ISSUE-2 root cause: _merge_live_agent_profile built a new AgentProfile without
    passing features/custom_prompt, so those fields reverted to their dataclass defaults
    ({} and None) whenever the gateway was online and source=live was used.
    """

    async def _fake_agent_config(self, *, target_node_id: str, agent_id: str):  # noqa: ARG001, ARG002
        # Live snapshot from Gateway — intentionally omits features/custom_prompt,
        # which is the real-world case (Gateway doesn't carry IM-owned config fields).
        return {
            "display_name": "Live Agent",
            "system_prompt": "Live prompt",
            "skills": [],
            "tool_allowlist": ["memory"],
        }

    monkeypatch.setattr(GatewayHandler, "request_agent_config", _fake_agent_config)

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner_live", display_name="OwnerLive")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-live", node_name="LiveNode")
        profiles.upsert_profile(
            agent_id="agent-live",
            owner_id=owner.owner_id,
            node_id="node-live",
            display_name="Live Agent",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=["memory"],
            group_reply_policy="manual",
            default_model=None,
            workspace_root=None,
            features={"memory_curation": False},
            custom_prompt="You are my legal advisor.",
        )

        # source=live will call _fake_agent_config and then _merge_live_agent_profile
        resp = client.get("/im/v1/agents/agent-live/config?source=live")
        assert resp.status_code == 200
        body = resp.json()
        # After merge, IM-owned fields must survive even though the live snapshot omits them
        assert body["features"] == {"memory_curation": False}, (
            "_merge_live_agent_profile must preserve features from the persisted profile (ISSUE-2)"
        )
        assert body["custom_prompt"] == "You are my legal advisor.", (
            "_merge_live_agent_profile must preserve custom_prompt from the persisted profile (ISSUE-2)"
        )


def test_agent_prompt_preview_proxy_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IM proxy route POST /im/v1/agents/{id}/prompt-preview forwards to Gateway.

    feat-379-M2 R5: IM must forward the request to Gateway via
    request_prompt_preview and return the assembled prompt to the caller.
    """

    async def _fake_request_prompt_preview(
        self,  # noqa: ARG001
        *,
        target_node_id: str,  # noqa: ARG001
        agent_id: str,  # noqa: ARG001
        workspace_root: str,  # noqa: ARG001
        features: dict,  # noqa: ARG001
        custom_prompt,  # noqa: ARG001
        tool_ids: list,  # noqa: ARG001
        scenario: str,  # noqa: ARG001
        skill_ids: list | None = None,  # noqa: ARG001
        timeout_seconds: float = 10.0,  # noqa: ARG001
    ) -> dict:
        return {"prompt": "You are a helpful assistant.", "section_count": 2}

    monkeypatch.setattr(
        GatewayHandler, "request_prompt_preview", _fake_request_prompt_preview
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-1", node_name="MacBook")
        profiles.upsert_profile(
            agent_id="agent-prev",
            owner_id=owner.owner_id,
            display_name="Preview Agent",
            description="",
            system_prompt="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="always",
            default_model=None,
            workspace_root=None,
            node_id="node-1",
        )
        response = client.post(
            "/im/v1/agents/agent-prev/prompt-preview",
            json={
                "features": {"memory_curation": True},
                "custom_prompt": "Be concise.",
                "tool_ids": ["read"],
                "scenario": "direct",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "prompt" in body
    assert "section_count" in body
    assert body["prompt"] == "You are a helpful assistant."
    assert body["section_count"] == 2


def test_agent_capabilities_features_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    monkeypatch.setattr(
        GatewayHandler, "request_agent_capabilities", _fake_agent_capabilities
    )

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
    required_feature_fields = {
        "key",
        "label_i18n",
        "help_i18n",
        "default_on",
        "available",
    }
    for feat in features:
        assert required_feature_fields.issubset(set(feat)), f"missing fields in {feat}"
    # spot-check first feature values round-tripped correctly
    assert features[0]["key"] == "web_search"
    assert features[0]["available"] is True
    assert features[1]["key"] == "memory"
    assert features[1]["available"] is False
    assert features[1]["requires_tool"] is None


# ---------------------------------------------------------------------------
# feat-383-M1 R3: skill_ids + agent_id_hint → workspace_root derive
# ---------------------------------------------------------------------------


def test_agent_prompt_preview_forwards_skill_ids_to_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /im/v1/agents/{id}/prompt-preview must forward skill_ids to request_prompt_preview.

    feat-383-M1: skill_ids from the request body must reach the Gateway call.
    """
    captured: list[dict] = []

    async def _fake_request_prompt_preview(
        self,  # noqa: ARG001
        *,
        target_node_id: str,  # noqa: ARG001
        agent_id: str,  # noqa: ARG001
        workspace_root: str,  # noqa: ARG001
        features: dict,  # noqa: ARG001
        custom_prompt,  # noqa: ARG001
        tool_ids: list,  # noqa: ARG001
        scenario: str,  # noqa: ARG001
        skill_ids: list | None = None,  # noqa: ARG001
        timeout_seconds: float = 10.0,  # noqa: ARG001
    ) -> dict:
        captured.append({"skill_ids": list(skill_ids or [])})
        return {"prompt": "preview", "section_count": 1}

    monkeypatch.setattr(
        GatewayHandler, "request_prompt_preview", _fake_request_prompt_preview
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        profiles = AgentProfileRepository(app.state.connection)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(node_id="node-skill", node_name="MacBook")
        profiles.upsert_profile(
            agent_id="agent-skill",
            owner_id=owner.owner_id,
            display_name="Skill Agent",
            description="",
            system_prompt="",
            skills=["plan"],
            tool_allowlist=["read"],
            group_reply_policy="always",
            default_model=None,
            workspace_root=None,
            node_id="node-skill",
        )
        response = client.post(
            "/im/v1/agents/agent-skill/prompt-preview",
            json={
                "features": {},
                "custom_prompt": None,
                "tool_ids": ["read"],
                "skill_ids": ["plan", "review"],
                "scenario": "direct",
            },
        )

    assert response.status_code == 200
    assert len(captured) == 1, "request_prompt_preview must have been called"
    assert captured[0]["skill_ids"] == ["plan", "review"], (
        f"skill_ids must be forwarded to Gateway, got: {captured[0]['skill_ids']}"
    )


def test_node_prompt_preview_derives_workspace_root_from_agent_id_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /im/v1/nodes/{id}/prompt-preview must derive workspace_root from agent_id_hint.

    feat-383-M1: when agent_id_hint is provided, IM derives workspace_root via
    managed_workspace_root(agent_id_hint) and forwards it to Gateway.
    """
    captured: list[dict] = []

    async def _fake_request_node_prompt_preview(
        self,  # noqa: ARG001
        *,
        target_node_id: str,  # noqa: ARG001
        features: dict,  # noqa: ARG001
        custom_prompt,  # noqa: ARG001
        tool_ids: list,  # noqa: ARG001
        scenario: str,  # noqa: ARG001
        workspace_root: str = "",  # noqa: ARG001
        skill_ids: list | None = None,  # noqa: ARG001
        timeout_seconds: float = 10.0,  # noqa: ARG001
    ) -> dict:
        captured.append(
            {"workspace_root": workspace_root, "skill_ids": list(skill_ids or [])}
        )
        return {"prompt": "node-preview", "section_count": 1}

    monkeypatch.setattr(
        GatewayHandler, "request_node_prompt_preview", _fake_request_node_prompt_preview
    )

    from IM.domain.models import managed_workspace_root

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-create", node_name="MacBook", owner_id=owner.owner_id
        )

        response = client.post(
            "/im/v1/nodes/node-create/prompt-preview",
            json={
                "features": {},
                "custom_prompt": None,
                "tool_ids": [],
                "skill_ids": ["code-review"],
                "agent_id_hint": "new-agent-x",
                "scenario": "direct",
            },
        )

    assert response.status_code == 200
    assert len(captured) == 1, "request_node_prompt_preview must have been called"
    expected_ws = managed_workspace_root("new-agent-x")
    assert captured[0]["workspace_root"] == expected_ws, (
        f"workspace_root must be derived from agent_id_hint 'new-agent-x', "
        f"expected {expected_ws!r}, got: {captured[0]['workspace_root']!r}"
    )
    assert captured[0]["skill_ids"] == ["code-review"], (
        f"skill_ids must be forwarded to Gateway, got: {captured[0]['skill_ids']}"
    )


def test_node_prompt_preview_workspace_root_empty_when_no_agent_id_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /im/v1/nodes/{id}/prompt-preview must pass empty workspace_root when no agent_id_hint.

    feat-383-M1: without agent_id_hint, workspace_root should be empty string.
    """
    captured: list[dict] = []

    async def _fake_request_node_prompt_preview(
        self,  # noqa: ARG001
        *,
        target_node_id: str,  # noqa: ARG001
        features: dict,  # noqa: ARG001
        custom_prompt,  # noqa: ARG001
        tool_ids: list,  # noqa: ARG001
        scenario: str,  # noqa: ARG001
        workspace_root: str = "",  # noqa: ARG001
        skill_ids: list | None = None,  # noqa: ARG001
        timeout_seconds: float = 10.0,  # noqa: ARG001
    ) -> dict:
        captured.append({"workspace_root": workspace_root})
        return {"prompt": "node-preview-empty", "section_count": 1}

    monkeypatch.setattr(
        GatewayHandler, "request_node_prompt_preview", _fake_request_node_prompt_preview
    )

    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        nodes = NodeRepository(app.state.connection)
        nodes.upsert_node(
            node_id="node-empty", node_name="MacBook", owner_id=owner.owner_id
        )

        response = client.post(
            "/im/v1/nodes/node-empty/prompt-preview",
            json={
                "features": {},
                "custom_prompt": None,
                "tool_ids": [],
                "scenario": "direct",
            },
        )

    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0]["workspace_root"] == "", (
        f"workspace_root must be empty when no agent_id_hint, got: {captured[0]['workspace_root']!r}"
    )
