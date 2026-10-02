"""Runtime skill activation stays scoped to the authenticated machine's agents."""

from tests.im_service._auth_helpers import gateway_socket
from tests.im_service.integration.conftest import (
    make_app_client,
    register_user,
    authorize,
)
from .test_gateway_auth_boundary import _registration
from .test_agent_config_api import _applied_config_operation


def test_machine_can_add_own_skills_without_browser_management_or_cross_node_access(
    tmp_path,
):
    with make_app_client(tmp_path) as client:
        owner = register_user(client, username="skill-owner")
        authorize(client, owner)
        client.app.state.gateway_control.request_agent_config_apply = (
            _applied_config_operation
        )
        with gateway_socket(client) as ws:
            ws.send_json(_registration(node_id="skills", key_seed=b"s" * 32))
            token = ws.receive_json()["payload"]["gateway_access_token"]
            machine = {"Authorization": "Bearer " + token}
            route = "/im/v1/agents/agent-skills/skills/enable"
            db = client.app.state.connection
            db.execute(
                "UPDATE agent_profiles SET skills_json='[\"original\"]',work_mode='global' WHERE agent_id='agent-skills'"
            )
            db.commit()
            original = client.get(
                "/im/v1/agents/agent-skills/config?source=mirror", headers=machine
            ).json()
            version = original["profile_version"]
            assert (
                client.post(
                    route, json={"profile_version": version, "skills": ["new"]}
                ).status_code
                == 401
            )
            assert (
                client.post(
                    route,
                    headers=machine,
                    json={
                        "profile_version": version,
                        "skills": ["new"],
                        "tool_allowlist": ["bash"],
                    },
                ).status_code
                == 422
            )
            result = client.post(
                route,
                headers=machine,
                json={"profile_version": version, "skills": ["new"]},
            )
            assert result.status_code == 200, result.text
            assert result.json()["skills"] == ["original", "new"]
            for key in ("work_mode", "tool_allowlist", "default_model", "features"):
                assert result.json()[key] == original[key]
            assert (
                client.post(
                    route,
                    headers=machine,
                    json={"profile_version": version, "skills": ["stale"]},
                ).status_code
                == 409
            )
            with gateway_socket(client) as other:
                other.send_json(
                    _registration(node_id="other-skills", key_seed=b"o" * 32)
                )
                assert other.receive_json()["type"] == "ack"
                assert (
                    client.post(
                        "/im/v1/agents/agent-other-skills/skills/enable",
                        headers=machine,
                        json={"profile_version": 1, "skills": ["new"]},
                    ).status_code
                    == 404
                )
            db.execute(
                "UPDATE users SET membership_status='suspended' WHERE id=?", (owner.id,)
            )
            db.commit()
            assert (
                client.post(
                    route,
                    headers=machine,
                    json={"profile_version": version + 1, "skills": ["revoked"]},
                ).status_code
                == 401
            )
