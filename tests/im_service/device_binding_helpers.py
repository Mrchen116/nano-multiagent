"""Drive the real device proof protocol from an explicitly local test device."""

from personal_assistant.channels.channel_credentials import GatewayChannelKeyStore
from personal_assistant.gateway.device_binding import (
    open_challenge,
    confirmation_proof,
    rewrap_channels,
)


def prepare_binding(client, tmp_path, *, node_id):
    key = GatewayChannelKeyStore(tmp_path / f"{node_id}.pem").load_or_create()
    connection = client.app.state.connection
    node = connection.execute(
        "SELECT owner_id FROM nodes WHERE node_id=?", (node_id,)
    ).fetchone()
    if node is not None:
        from IM.cli.enroll_device import enroll_device
        from pathlib import Path

        db_path = Path(connection.execute("PRAGMA database_list").fetchone()["file"])
        enroll_device(
            db_path=db_path,
            node_id=node_id,
            device_key_path=tmp_path / f"{node_id}.pem",
        )
    response = client.post(
        "/im/v1/device-binding/start",
        json={
            "node_id": node_id,
            "node_name": node_id,
            "public_key": key.public_key,
            "key_id": key.key_id,
        },
    )
    assert response.status_code == 200, response.text
    local = response.json()
    auth = {k: local[k] for k in ("operation_id", "operation_token")}
    challenge = open_challenge(key, local["challenge"])
    assert (
        client.post(
            "/im/v1/device-binding/prove", json={**auth, "challenge": challenge}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/im/v1/device-binding/accept",
            json={"browser_token": local["browser_token"]},
        ).status_code
        == 200
    )
    prepared = client.post("/im/v1/device-binding/prepare", json=auth).json()
    return {
        **auth,
        "proof": confirmation_proof(challenge, prepared["confirmation"]),
        "envelopes": rewrap_channels(
            key, prepared["snapshot"], prepared["target_owner"]
        ),
    }


def complete_binding(client, tmp_path, *, node_id):
    commit = prepare_binding(client, tmp_path, node_id=node_id)
    response = client.post("/im/v1/device-binding/commit", json=commit)
    assert response.status_code == 200, response.text
    auth = {k: commit[k] for k in ("operation_id", "operation_token")}
    return client.post("/im/v1/device-binding/recover", json=auth).json()
