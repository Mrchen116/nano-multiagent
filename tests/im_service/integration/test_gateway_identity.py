"""A machine can resolve only its authenticated node and owner identity."""

from tests.im_service._auth_helpers import gateway_socket
from tests.im_service.integration.conftest import (
    make_app_client,
    register_user,
    authorize,
)
from .test_gateway_auth_boundary import _registration


def test_gateway_identity_is_machine_only_and_revoked_with_membership(tmp_path):
    with make_app_client(tmp_path) as client:
        owner = register_user(client, username="identity-owner")
        authorize(client, owner)
        route = "/im/v1/gateway/identity"
        assert client.get(route).status_code == 401
        with gateway_socket(client) as ws:
            ws.send_json(_registration(node_id="identity-node", key_seed=b"i" * 32))
            token = ws.receive_json()["payload"]["gateway_access_token"]
            machine = {"Authorization": "Bearer " + token}
            response = client.get(route, headers=machine)
            assert response.status_code == 200, response.text
            assert response.json() == {
                "node_id": "identity-node",
                "owner_id": owner.id,
            }
            for human_route in ("/im/v1/me", "/im/v1/nodes"):
                assert client.get(human_route, headers=machine).status_code == 401
            db = client.app.state.connection
            db.execute(
                "UPDATE users SET membership_status='suspended' WHERE id=?", (owner.id,)
            )
            db.commit()
            assert client.get(route, headers=machine).status_code == 401
