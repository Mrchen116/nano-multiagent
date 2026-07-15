"""Gateway websocket authentication and owner-isolation regressions."""

from __future__ import annotations

from functools import partial
from pathlib import Path
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from IM.infra.channel_credentials import generate_channel_key_pair
from tests.im_service.integration.conftest import (
    authorize,
    make_app_client,
    register_user,
)


def _registration(*, node_id: str, key_seed: bytes) -> dict[str, object]:
    pair = generate_channel_key_pair(private_seed=key_seed)
    return {
        "type": "node.register",
        "payload": {
            "node_id": node_id,
            "node_name": node_id,
            "agents": ["agent-secure"],
            "capabilities": {"channel_bootstrap": True},
            "credential_key_id": pair.key_id,
            "credential_algorithm": "X25519-HKDF-SHA256-AES-256-GCM",
            "credential_public_key": pair.public_key,
        },
    }


def test_gateway_websocket_rejects_missing_bearer_before_registration(
    tmp_path: Path,
) -> None:
    """An unauthenticated socket cannot create a node or enter the connection map."""
    with make_app_client(tmp_path) as client:
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect("/im/ws/gateway") as websocket:
                websocket.send_json(_registration(node_id="node-anon", key_seed=b"a" * 32))
                websocket.receive_json()

        assert caught.value.code == 1008
        assert client.app.state.connection.execute(
            "SELECT 1 FROM nodes WHERE node_id = 'node-anon'"
        ).fetchone() is None
        connected = client.portal.call(
            partial(
                client.app.state.gateway_handler.snapshot_connection,
                node_id="node-anon",
            )
        )
        assert connected is None


def test_authenticated_wrong_owner_cannot_replace_bound_node_socket_or_key(
    tmp_path: Path,
) -> None:
    """A valid token from another tenant cannot hijack an already-bound node."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="gateway-alice")
        bob = register_user(client, username="gateway-bob")
        authorize(client, alice)
        original = _registration(node_id="node-owned", key_seed=b"o" * 32)

        with client.websocket_connect("/im/ws/gateway") as owner_socket:
            owner_socket.send_json(original)
            assert owner_socket.receive_json()["type"] == "ack"
            start = client.post(
                "/im/v1/bind", json={"action": "start", "node_id": "node-owned"}
            )
            confirmed = client.post(
                "/im/v1/bind",
                json={"action": "confirm", "bind_id": start.json()["bind_id"]},
            )
            assert confirmed.status_code == 201

            expected_key_id = original["payload"]["credential_key_id"]
            for _ in range(50):
                row = client.app.state.connection.execute(
                    "SELECT key_id FROM node_credential_keys WHERE node_id = ?",
                    ("node-owned",),
                ).fetchone()
                if row is not None:
                    break
                time.sleep(0.01)
            assert row is not None and row["key_id"] == expected_key_id

            authorize(client, bob)
            with client.websocket_connect("/im/ws/gateway") as attacker_socket:
                attacker_socket.send_json(
                    _registration(node_id="node-owned", key_seed=b"x" * 32)
                )
                rejection = attacker_socket.receive_json()
                assert rejection == {
                    "type": "error",
                    "payload": {
                        "code": "gateway_owner_mismatch",
                        "message": "node is bound to another owner",
                    },
                }
                with pytest.raises(WebSocketDisconnect) as caught:
                    attacker_socket.receive_json()
                assert caught.value.code == 1008

            connection = client.portal.call(
                partial(
                    client.app.state.gateway_handler.snapshot_connection,
                    node_id="node-owned",
                )
            )
            assert connection is not None
            assert connection.owner_id == alice.owner_id
            assert connection.credential_key_id == expected_key_id
            key_row = client.app.state.connection.execute(
                "SELECT owner_id, key_id FROM node_credential_keys WHERE node_id = ?",
                ("node-owned",),
            ).fetchone()
            assert tuple(key_row) == (alice.owner_id, expected_key_id)
