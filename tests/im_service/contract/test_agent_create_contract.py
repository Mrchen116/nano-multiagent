"""Contract tests for creating IM agent profiles."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.nodes import NodeRepository

from tests.im_service._auth_helpers import authorize, register_user


def test_agent_create_contract_shape_and_validation(tmp_path: Path) -> None:
    """Expose stable node-scoped create response fields and reject unknown/disconnected nodes."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook", owner_id=owner.owner_id
        )

        async def fake_request_agent_create(
            *,
            target_node_id: str,
            payload: dict[str, object],
            operation_id: str,
            candidate_fingerprint: str,
            timeout_seconds: float = 5.0,
        ):
            del timeout_seconds
            if target_node_id != "node-1":
                return None
            return {
                "operation_id": operation_id,
                "status": "applied",
                "agent": {
                    "agent_id": payload["agent_id"],
                    "display_name": payload["display_name"],
                    "description": "first runtime agent",
                    "custom_prompt": payload["custom_prompt"],
                    "features": payload["features"],
                    "skills": payload["skills"],
                    "tool_allowlist": payload["tool_allowlist"],
                    "group_reply_policy": payload["group_reply_policy"],
                    "default_model": payload["default_model"],
                    "workspace_root": "/srv/agents/agent-1",
                    "workspace_is_default": True,
                },
                "candidate_fingerprint": candidate_fingerprint,
            }

        app.state.gateway_control.request_agent_create = fake_request_agent_create

        created = client.post(
            "/im/v1/nodes/node-1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "description": "first runtime agent",
                "custom_prompt": "You are Alpha.",
                "features": {"memory": True},
                "skills": ["plan"],
                "tool_allowlist": ["read"],
                "group_reply_policy": "MENTION",
                "default_model": "claude-sonnet-4",
            },
        )
        assert created.status_code == 201
        # feat-379-M5: features + custom_prompt are now part of AgentConfigResponse
        # feat-394: heartbeat_json carries cadence (every/active_hours).
        # feat-394 M9-E: cron_json removed — cron enable lives in features["cron_scheduling"].
        assert set(created.json()) == {
            "agent_id",
            "owner_id",
            "node_id",
            "display_name",
            "description",
            "skills",
            "tool_allowlist",
            "group_reply_policy",
            "default_model",
            "reasoning_effort",
            "workspace_root",
            "workspace_is_default",
            "profile_version",
            "updated_at",
            "features",
            "custom_prompt",
            "heartbeat_json",
        }
        assert created.json()["node_id"] == "node-1"
        assert created.json()["workspace_root"] == "/srv/agents/agent-1"
        assert created.json()["workspace_is_default"] is True
        assert isinstance(created.json()["updated_at"], str)
        assert created.json()["profile_version"] == 1

        duplicate = client.post(
            "/im/v1/nodes/node-1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha duplicate",
                "description": "duplicate",
                "custom_prompt": "You are Alpha duplicate.",
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
                "custom_prompt": "You are Beta.",
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


def test_agent_create_surfaces_gateway_workspace_errors_without_persisting(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook", owner_id=owner.owner_id
        )

        async def fake_request_agent_create(**_kwargs):
            return {
                "status": "rejected",
                "error_code": "workspace_confirmation_required",
                "message": "workspace already exists",
                "agent_id": "agent-1",
            }

        app.state.gateway_control.request_agent_create = fake_request_agent_create
        response = client.post(
            "/im/v1/nodes/node-1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "workspace_root": "/srv/existing",
            },
        )

        assert response.status_code == 409
        assert response.json() == {
            "code": "workspace_confirmation_required",
            "detail": "workspace already exists",
            "agent_id": "agent-1",
        }
        assert (
            app.state.connection.execute(
                "SELECT 1 FROM agent_profiles WHERE agent_id = ?", ("agent-1",)
            ).fetchone()
            is None
        )


def test_agent_create_defaults_omitted_skills_from_node_capabilities(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook"
        )

        async def fake_request_node_capabilities(
            *, target_node_id: str, timeout_seconds: float = 5.0
        ):
            del timeout_seconds
            assert target_node_id == "node-1"
            return {
                "skills": [
                    {"name": "pa-global", "description": "", "default_on": True},
                    {"name": "compat-claude", "description": "", "default_on": False},
                ]
            }

        async def fake_request_agent_create(
            *,
            target_node_id: str,
            payload: dict[str, object],
            operation_id: str,
            candidate_fingerprint: str,
            timeout_seconds: float = 5.0,
        ):
            del timeout_seconds
            assert target_node_id == "node-1"
            return {
                "operation_id": operation_id,
                "status": "applied",
                "agent": {
                    "agent_id": payload["agent_id"],
                    "display_name": payload["display_name"],
                    "custom_prompt": payload["custom_prompt"],
                    "features": payload["features"],
                    "skills": payload["skills"],
                    "tool_allowlist": payload["tool_allowlist"],
                    "group_reply_policy": payload["group_reply_policy"],
                    "default_model": payload["default_model"],
                    "workspace_root": "/srv/agents/agent-1",
                },
                "candidate_fingerprint": candidate_fingerprint,
            }

        app.state.gateway_control.request_node_capabilities = (
            fake_request_node_capabilities
        )
        app.state.gateway_control.request_agent_create = fake_request_agent_create

        created = client.post(
            "/im/v1/nodes/node-1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "description": "first runtime agent",
                "custom_prompt": "You are Alpha.",
                "tool_allowlist": ["read"],
                "group_reply_policy": "MENTION",
                "default_model": "claude-sonnet-4",
            },
        )

        assert created.status_code == 201
        assert created.json()["skills"] == ["pa-global"]


def test_agent_create_omits_skills_when_capabilities_unavailable(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner", display_name="Owner")
        authorize(client, owner)
        NodeRepository(app.state.connection).upsert_node(
            node_id="node-1", node_name="MacBook"
        )
        seen_payloads: list[dict[str, object]] = []

        async def fake_request_node_capabilities(
            *, target_node_id: str, timeout_seconds: float = 5.0
        ):
            del target_node_id, timeout_seconds
            return None

        async def fake_request_agent_create(
            *,
            target_node_id: str,
            payload: dict[str, object],
            operation_id: str,
            candidate_fingerprint: str,
            timeout_seconds: float = 5.0,
        ):
            del timeout_seconds
            assert target_node_id == "node-1"
            seen_payloads.append(payload)
            assert "skills" not in payload
            return {
                "operation_id": operation_id,
                "status": "applied",
                "agent": {
                    "agent_id": payload["agent_id"],
                    "display_name": payload["display_name"],
                    "custom_prompt": payload["custom_prompt"],
                    "features": payload["features"],
                    "skills": ["gateway-default"],
                    "tool_allowlist": payload["tool_allowlist"],
                    "group_reply_policy": payload["group_reply_policy"],
                    "default_model": payload["default_model"],
                    "workspace_root": "/srv/agents/agent-1",
                },
                "candidate_fingerprint": candidate_fingerprint,
            }

        app.state.gateway_control.request_node_capabilities = (
            fake_request_node_capabilities
        )
        app.state.gateway_control.request_agent_create = fake_request_agent_create

        created = client.post(
            "/im/v1/nodes/node-1/agents",
            json={
                "agent_id": "agent-1",
                "owner_id": owner.owner_id,
                "display_name": "Alpha",
                "description": "first runtime agent",
                "custom_prompt": "You are Alpha.",
                "tool_allowlist": ["read"],
                "group_reply_policy": "MENTION",
                "default_model": "claude-sonnet-4",
            },
        )

        assert created.status_code == 201
        assert seen_payloads
        assert created.json()["skills"] == ["gateway-default"]
