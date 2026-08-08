"""Recovery contract for Gateway registration seeds after a lost create response."""

from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from tests.im_service._auth_helpers import authorize, register_user


def test_bound_registration_seed_claims_gateway_canonical_alias_once(tmp_path: Path) -> None:
    """A bound Gateway seed accepts only its matching canonical create retry."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="bound-owner")
        authorize(client, owner)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-bound-seed",
                        "node_name": "Gateway",
                        "version": "1.0.0",
                        "agents": [],
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            bind_start = client.post(
                "/im/v1/bind",
                json={"action": "start", "node_id": "node-bound-seed"},
            )
            assert bind_start.status_code == 201
            assert client.post(
                "/im/v1/bind",
                json={"action": "confirm", "bind_id": bind_start.json()["bind_id"]},
            ).status_code == 201
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-bound-seed",
                        "node_name": "Gateway",
                        "version": "1.0.1",
                        "agents": ["bound-seed"],
                        "agent_workspaces": {"bound-seed": "/gateway/bound-seed"},
                        "agent_workspace_is_default": {"bound-seed": False},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            async def fake_request_agent_create(**kwargs):
                requested = kwargs["payload"]
                root = requested["workspace_root"]
                returned_root = (
                    "/gateway/bound-seed"
                    if root in {"/gateway/bound-seed", "/gateway/staging/../bound-seed"}
                    else root
                )
                return {
                    "agent_id": "bound-seed",
                    "display_name": "Bound Seed",
                    "description": "Recovered after a lost response.",
                    "workspace_root": returned_root,
                    "workspace_is_default": False,
                }

            app.state.gateway_control.request_agent_create = fake_request_agent_create
            payload = {
                "agent_id": "bound-seed",
                "owner_id": "",
                "display_name": "Bound Seed",
                "description": "Recovered after a lost response.",
                "skills": [],
                "tool_allowlist": [],
                "group_reply_policy": "MENTION",
                "workspace_root": "/gateway/staging/../bound-seed",
            }
            claimed = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            repeated = client.post(
                "/im/v1/nodes/node-bound-seed/agents", json=payload
            )
            changed_root = client.post(
                "/im/v1/nodes/node-bound-seed/agents",
                json={**payload, "workspace_root": "/gateway/other"},
            )
            changed_name = client.post(
                "/im/v1/nodes/node-bound-seed/agents",
                json={**payload, "display_name": "Other Name"},
            )

        assert claimed.status_code == 201, claimed.text
        assert repeated.status_code == 409
        assert changed_root.status_code == 409
        assert changed_name.status_code == 409
        stored = app.state.connection.execute(
            "SELECT owner_id, display_name, description, workspace_root, "
            "workspace_is_default, registration_seed "
            "FROM agent_profiles WHERE agent_id = ?",
            ("bound-seed",),
        ).fetchone()
        assert dict(stored) == {
            "owner_id": owner.owner_id,
            "display_name": "Bound Seed",
            "description": "Recovered after a lost response.",
            "workspace_root": "/gateway/bound-seed",
            "workspace_is_default": 0,
            "registration_seed": 0,
        }
