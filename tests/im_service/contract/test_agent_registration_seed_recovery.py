"""Recovery contracts for durable Gateway-first Agent create operations."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agent_config_operations import AgentConfigOperationRepository
from tests.im_service._auth_helpers import authorize, register_user


def _register_seed(
    client: TestClient,
    *,
    agent_id: str,
    workspace_root: str,
) -> None:
    with client.websocket_connect("/im/ws/gateway") as websocket:
        websocket.send_json(
            {
                "type": "node.register",
                "payload": {
                    "node_id": "node-seed",
                    "node_name": "Gateway",
                    "version": "1",
                    "agents": [agent_id],
                    "agent_workspaces": {agent_id: workspace_root},
                    "agent_workspace_is_default": {agent_id: False},
                },
            }
        )
        assert websocket.receive_json()["type"] == "ack"


def _payload(agent_id: str) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "owner_id": "",
        "display_name": "Recovered Agent",
        "description": "Recovered after a lost response.",
        "skills": [],
        "tool_allowlist": [],
        "group_reply_policy": "MENTION",
        "workspace_root": "/gateway/recovered-agent",
    }


def test_ordinary_registration_is_not_claimable(tmp_path: Path) -> None:
    """An advertised local Agent cannot be claimed without an active IM operation."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        _register_seed(
            client, agent_id="prehosted-agent", workspace_root="/gateway/prehosted"
        )
        calls: list[object] = []

        async def unexpected_create(**kwargs):
            calls.append(kwargs)
            raise AssertionError("prehosted registration must not reach Gateway create")

        app.state.gateway_control.request_agent_create = unexpected_create
        response = client.post(
            "/im/v1/nodes/node-seed/agents", json=_payload("prehosted-agent")
        )

    assert response.status_code == 409
    assert calls == []


def test_lost_create_response_claims_matching_registration_seed(tmp_path: Path) -> None:
    """A retry recovers the durable operation and claims only its matching seed."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        _register_seed(client, agent_id="placeholder", workspace_root="/gateway/placeholder")
        payload = _payload("recovered-agent")

        async def lost_response(**_kwargs):
            return None

        app.state.gateway_control.request_agent_create = lost_response
        initial = client.post("/im/v1/nodes/node-seed/agents", json=payload)
        operations = AgentConfigOperationRepository(app.state.connection)
        operation = operations.get_active(
            agent_id="recovered-agent", owner_id=owner.owner_id
        )
        assert operation is not None
        _register_seed(
            client,
            agent_id="recovered-agent",
            workspace_root="/gateway/recovered-agent",
        )
        assert app.state.connection.execute(
            "SELECT registration_seed FROM agent_profiles WHERE agent_id = ?",
            ("recovered-agent",),
        ).fetchone()["registration_seed"] == 1

        async def recovered_status(**_kwargs):
            return {
                "operation_id": operation.operation_id,
                "candidate_fingerprint": operation.candidate_fingerprint,
                "status": "applied",
                "agent": {
                    **operation.candidate,
                    "workspace_root": "/gateway/recovered-agent",
                    "workspace_is_default": False,
                    "display_name": "Recovered Agent",
                },
            }

        app.state.gateway_control.request_agent_config_operation_status = recovered_status
        recovered = client.post("/im/v1/nodes/node-seed/agents", json=payload)
        repeated = client.post("/im/v1/nodes/node-seed/agents", json=payload)
        stored = app.state.connection.execute(
            "SELECT owner_id, workspace_root, registration_seed "
            "FROM agent_profiles WHERE agent_id = ?",
            ("recovered-agent",),
        ).fetchone()

    assert initial.status_code == 503
    assert recovered.status_code == 201, recovered.text
    assert repeated.status_code == 409
    assert dict(stored) == {
        "owner_id": owner.owner_id,
        "workspace_root": "/gateway/recovered-agent",
        "registration_seed": 0,
    }
