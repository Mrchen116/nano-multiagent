"""Exercise real HTTP proof, browser acceptance and runtime WS admission."""

from personal_assistant.channels.channel_credentials import GatewayChannelKeyStore
from personal_assistant.gateway.device_binding import open_challenge, confirmation_proof
from .conftest import make_app_client, register_user, authorize


def test_real_binding_routes_admit_only_proven_node_runtime(tmp_path):
    with make_app_client(tmp_path) as client:
        user = register_user(client, username="recipient")
        authorize(client, user)
        key = GatewayChannelKeyStore(tmp_path / "private.pem").load_or_create()
        start = client.post(
            "/im/v1/device-binding/start",
            json={
                "node_id": "node-new",
                "node_name": "Device",
                "public_key": key.public_key,
                "key_id": key.key_id,
            },
        )
        assert start.status_code == 200, start.text
        local = start.json()
        assert "#token=" in local["bind_url"] and "?token=" not in local["bind_url"]
        auth = {k: local[k] for k in ("operation_id", "operation_token")}
        assert (
            client.post(
                "/im/v1/device-binding/accept",
                json={"browser_token": local["browser_token"]},
            ).status_code
            == 409
        )
        challenge = open_challenge(key, local["challenge"])
        assert (
            client.post(
                "/im/v1/device-binding/prove", json={**auth, "challenge": challenge}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/im/v1/device-binding/inspect",
                json={"browser_token": local["browser_token"]},
            ).json()["state"]
            == "awaiting_account"
        )
        assert (
            client.post(
                "/im/v1/device-binding/accept",
                json={"browser_token": local["browser_token"]},
            ).status_code
            == 200
        )
        assert (
            client.app.state.connection.execute(
                "SELECT * FROM nodes WHERE node_id='node-new'"
            ).fetchone()
            is None
        )
        prepared = client.post("/im/v1/device-binding/prepare", json=auth).json()
        response = client.post(
            "/im/v1/device-binding/commit",
            json={
                **auth,
                "proof": confirmation_proof(challenge, prepared["confirmation"]),
                "envelopes": {},
            },
        )
        assert response.status_code == 200, response.text
        runtime = client.post("/im/v1/device-binding/recover", json=auth).json()
        assert runtime["owner_id"] == user.owner_id
        with client.websocket_connect(
            "/im/ws/gateway",
            headers={"Authorization": "Bearer " + runtime["runtime_token"]},
        ) as ws:
            ws.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-new",
                        "agents": [],
                        **key.registration_payload(),
                    },
                }
            )
            frame = ws.receive_json()
            assert frame["type"] == "ack", frame
            assert frame["payload"]["node_id"] == "node-new"
        assert (
            client.post(
                "/im/v1/bind", json={"action": "start", "node_id": "node-new"}
            ).status_code
            == 400
        )
