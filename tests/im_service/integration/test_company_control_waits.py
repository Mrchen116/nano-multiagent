"""Company revocation stays available while real Gateway control frames wait."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from tests.im_service._auth_helpers import authorize, gateway_socket, register_user
from .test_agent_config_operation_flow import _seed_agent, _update_payload


@pytest.mark.parametrize("revoke", [False, True])
def test_same_agent_wait_and_logout_do_not_block_control_result(tmp_path, revoke):
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        _seed_agent(app, owner_id=owner.owner_id)
        with gateway_socket(client) as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-1",
                        "node_name": "Test",
                        "version": "1.0.0",
                        "agents": ["agent-1"],
                        "capabilities": {},
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"
            with ThreadPoolExecutor(max_workers=3) as pool:
                first = pool.submit(
                    client.patch, "/im/v1/agents/agent-1/config", json=_update_payload()
                )
                request = websocket.receive_json()
                assert request["type"] == "agent.config.apply"
                body = request["payload"]
                second = pool.submit(
                    client.patch, "/im/v1/agents/agent-1/config", json=_update_payload()
                )
                # This HTTP request must finish while both control requests remain pending.
                read = pool.submit(client.get, "/im/v1/auth/me")
                assert read.result(timeout=2).status_code == 200
                if revoke:
                    logout = pool.submit(
                        client.post,
                        "/im/v1/auth/logout",
                        json={"refresh_token": owner.refresh_token},
                    )
                    assert logout.result(timeout=2).status_code == 200
                websocket.send_json(
                    {
                        "type": "agent.config.apply.result",
                        "payload": {
                            "request_id": body["request_id"],
                            "node_id": "node-1",
                            "operation_id": body["operation_id"],
                            "status": "applied",
                            "candidate_fingerprint": body["candidate_fingerprint"],
                            "agent": body["agent"],
                        },
                    }
                )
                assert websocket.receive_json()["type"] == "ack"
                assert first.result(timeout=2).status_code == (401 if revoke else 200)
                assert second.result(timeout=2).status_code == (401 if revoke else 409)
            profile = AgentProfileRepository(app.state.connection).get_profile(
                agent_id="agent-1"
            )
            assert profile.profile_version == (1 if revoke else 2)
            assert not app.state.company_gate.locked()
            assert not app.state.connection.in_transaction
