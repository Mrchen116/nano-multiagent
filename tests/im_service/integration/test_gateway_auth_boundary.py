"""Gateway websocket authentication and owner-isolation regressions."""

from __future__ import annotations

from tests.im_service._auth_helpers import gateway_socket

from pathlib import Path
import threading
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from IM.infra.channel_credentials import generate_channel_key_pair
from tests.im_service.integration.conftest import (
    authorize,
    make_app_client,
    register_user,
)


def test_runtime_token_rotates_with_connection_and_never_grants_human_access(
    tmp_path: Path,
) -> None:
    """Only the current registered socket can authorize machine data requests."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="runtime-alice")
        authorize(client, alice)
        registration = _registration(node_id="runtime-node", key_seed=b"r" * 32)
        with gateway_socket(client) as first:
            first.send_json(registration)
            token = first.receive_json()["payload"]["gateway_access_token"]
            machine = {"Authorization": f"Bearer {token}"}
            for route in ("me", "nodes", "policies", "agents"):
                assert client.get(f"/im/v1/{route}", headers=machine).status_code == 401
            own_mirror = "/im/v1/agents/agent-runtime-node/config?source=mirror"
            assert client.get(own_mirror, headers=machine).status_code == 200
            assert (
                client.get(
                    own_mirror.replace("mirror", "live"), headers=machine
                ).status_code
                == 401
            )
            with gateway_socket(client) as other:
                other.send_json(_registration(node_id="other-node", key_seed=b"z" * 32))
                assert other.receive_json()["type"] == "ack"
                assert (
                    client.get(
                        "/im/v1/agents/agent-other-node/config?source=mirror",
                        headers=machine,
                    ).status_code
                    == 404
                )
            missing = (
                "/im/v1/conversations/missing/images/missing?agent_id=agent-secure"
            )
            assert client.get(missing, headers=machine).status_code == 404
            with gateway_socket(client) as replacement:
                replacement.send_json(registration)
                fresh = replacement.receive_json()["payload"]["gateway_access_token"]
                assert fresh != token
                assert client.get(missing, headers=machine).status_code == 401
                assert (
                    client.get(
                        missing, headers={"Authorization": f"Bearer {fresh}"}
                    ).status_code
                    == 404
                )
            assert (
                client.get(
                    missing, headers={"Authorization": f"Bearer {fresh}"}
                ).status_code
                == 401
            )


def _registration(*, node_id: str, key_seed: bytes) -> dict[str, object]:
    pair = generate_channel_key_pair(private_seed=key_seed)
    return {
        "type": "node.register",
        "payload": {
            "node_id": node_id,
            "node_name": node_id,
            "agents": [f"agent-{node_id}"],
            "capabilities": {},
            "credential_key_id": pair.key_id,
            "credential_algorithm": "X25519-HKDF-SHA256-AES-256-GCM",
            "credential_public_key": pair.public_key,
        },
    }


def test_registration_cannot_rebind_another_nodes_agent(tmp_path: Path) -> None:
    """Advertising a known Agent id cannot steal its node binding or membership."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="collision-alice")
        bob = register_user(client, username="collision-bob")
        authorize(client, alice)
        original = _registration(node_id="original", key_seed=b"e" * 32)
        original["payload"]["capabilities"] = {}
        with gateway_socket(client) as owner_socket:
            owner_socket.send_json(original)
            assert owner_socket.receive_json()["type"] == "ack"
            authorize(client, bob)
            with gateway_socket(client) as attacker:
                stolen = _registration(node_id="attacker", key_seed=b"f" * 32)
                stolen["payload"]["agents"] = original["payload"]["agents"]
                attacker.send_json(stolen)
                rejected = attacker.receive_json()
                assert rejected["type"] == "error", rejected
            row = client.app.state.connection.execute(
                "SELECT node_id, owner_id FROM agent_profiles WHERE agent_id = ?",
                (original["payload"]["agents"][0],),
            ).fetchone()
            assert tuple(row) == ("original", alice.id)


def test_gateway_websocket_rejects_missing_bearer_before_registration(
    tmp_path: Path,
) -> None:
    """An unauthenticated socket cannot create a node or enter the connection map."""
    with make_app_client(tmp_path) as client:
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect("/im/ws/gateway") as websocket:
                websocket.send_json(
                    _registration(node_id="node-anon", key_seed=b"a" * 32)
                )
                websocket.receive_json()

        assert caught.value.code == 1008
        assert (
            client.app.state.connection.execute(
                "SELECT 1 FROM nodes WHERE node_id = 'node-anon'"
            ).fetchone()
            is None
        )


def test_authenticated_wrong_owner_cannot_replace_bound_node_socket_or_key(
    tmp_path: Path,
) -> None:
    """A valid token from another tenant cannot hijack an already-bound node."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="gateway-alice")
        bob = register_user(client, username="gateway-bob")
        authorize(client, alice)
        original = _registration(node_id="node-owned", key_seed=b"o" * 32)

        with gateway_socket(client) as owner_socket:
            owner_socket.send_json(original)
            assert owner_socket.receive_json()["type"] == "ack"
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
            # Another human's token is never a device credential, even with a
            # valid company account and knowledge of this node id/public key.
            with pytest.raises(WebSocketDisconnect) as caught:
                with client.websocket_connect("/im/ws/gateway"):
                    pass
            assert caught.value.code == 1008

            authorize(client, alice)
            owner_socket.send_json(
                {
                    "type": "node.heartbeat",
                    "payload": {
                        "node_id": "node-owned",
                        "status": "online",
                        "last_error": "owner socket remains authoritative",
                    },
                }
            )
            assert owner_socket.receive_json()["type"] == "ack"
            visible_node = client.get("/im/v1/nodes").json()[0]
            assert visible_node["last_error"] == "owner socket remains authoritative"
            key_row = client.app.state.connection.execute(
                "SELECT owner_id, key_id FROM node_credential_keys WHERE node_id = ?",
                ("node-owned",),
            ).fetchone()
            assert tuple(key_row) == (alice.owner_id, expected_key_id)


def test_registered_socket_cannot_mutate_another_owners_node(
    tmp_path: Path,
) -> None:
    """A socket is the authority; a forged payload node cannot select another tenant."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="frame-alice")
        bob = register_user(client, username="frame-bob")
        authorize(client, alice)
        with gateway_socket(client) as alice_socket:
            alice_registration = _registration(node_id="node-alice", key_seed=b"a" * 32)
            alice_registration["payload"]["capabilities"] = {}
            alice_socket.send_json(alice_registration)
            assert alice_socket.receive_json()["type"] == "ack"

            authorize(client, bob)
            with gateway_socket(client) as bob_socket:
                bob_registration = _registration(node_id="node-bob", key_seed=b"b" * 32)
                bob_registration["payload"]["capabilities"] = {}
                bob_socket.send_json(bob_registration)
                assert bob_socket.receive_json()["type"] == "ack"
                alice_socket.send_json(
                    {
                        "type": "node.heartbeat",
                        "payload": {
                            "node_id": "node-bob",
                            "status": "online",
                            "last_error": "forged cross-owner degradation",
                        },
                    }
                )
                rejection = alice_socket.receive_json()
                assert rejection["payload"]["code"] == "gateway_owner_mismatch"

                authorize(client, bob)
                visible_node = next(
                    node
                    for node in client.get("/im/v1/nodes").json()
                    if node["node_id"] == "node-bob"
                )
                assert visible_node["status"] == "online"
                assert visible_node["last_error"] is None


def test_cross_owner_result_cannot_release_another_nodes_waiter(
    tmp_path: Path,
) -> None:
    """A forged result cannot satisfy another owner's public agent-create request."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="waiter-alice")
        bob = register_user(client, username="waiter-bob")
        authorize(client, alice)
        with gateway_socket(client) as alice_socket:
            alice_socket.send_json(
                _registration(node_id="waiter-a", key_seed=b"c" * 32)
            )
            assert alice_socket.receive_json()["type"] == "ack"

            authorize(client, bob)
            with gateway_socket(client) as bob_socket:
                bob_socket.send_json(
                    _registration(node_id="waiter-b", key_seed=b"d" * 32)
                )
                assert bob_socket.receive_json()["type"] == "ack"

                creation_result: dict[str, object] = {}

                def create_agent() -> None:
                    creation_result["response"] = client.post(
                        "/im/v1/nodes/waiter-b/agents",
                        headers={"Authorization": f"Bearer {bob.access_token}"},
                        json={
                            "agent_id": "agent-b",
                            "owner_id": bob.owner_id,
                            "display_name": "Agent B",
                            "description": "cross-owner result guard",
                            "custom_prompt": "You are Agent B.",
                            "skills": [],
                            "tool_allowlist": [],
                            "group_reply_policy": "MENTION",
                            "default_model": None,
                        },
                    )

                worker = threading.Thread(target=create_agent)
                worker.start()
                create_request = bob_socket.receive_json()
                assert create_request["type"] == "agent.create"
                request_id = create_request["payload"]["request_id"]
                operation_id = create_request["payload"]["operation_id"]
                candidate_fingerprint = create_request["payload"][
                    "candidate_fingerprint"
                ]
                alice_socket.send_json(
                    {
                        "type": "agent.created",
                        "payload": {
                            "request_id": request_id,
                            "node_id": "waiter-b",
                            "agent": {"agent_id": "forged-agent"},
                        },
                    }
                )
                rejection = alice_socket.receive_json()
                assert rejection["payload"]["code"] == "gateway_owner_mismatch"
                assert worker.is_alive()

                bob_socket.send_json(
                    {
                        "type": "agent.created",
                        "payload": {
                            "request_id": request_id,
                            "node_id": "waiter-b",
                            "operation_id": operation_id,
                            "status": "applied",
                            "candidate_fingerprint": candidate_fingerprint,
                            "agent": {
                                "agent_id": "agent-b",
                                "display_name": "Agent B",
                                "description": "cross-owner result guard",
                                "custom_prompt": "You are Agent B.",
                                "skills": [],
                                "tool_allowlist": [],
                                "group_reply_policy": "MENTION",
                                "default_model": None,
                                "reasoning_effort": None,
                                "workspace_root": str(tmp_path / "agent-b"),
                                "heartbeat_json": None,
                            },
                        },
                    }
                )
                assert bob_socket.receive_json()["type"] == "ack"
                worker.join(timeout=5)
                assert creation_result["response"].status_code == 201


def test_local_device_transfer_evicts_old_owner_socket(tmp_path: Path) -> None:
    """A complete local proof transfers the device, preserving its immutable key."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from tests.im_service.device_binding_helpers import complete_binding

    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="bind-alice")
        bob = register_user(client, username="bind-bob")
        authorize(client, bob)
        registration = _registration(node_id="node-prebound", key_seed=b"p" * 32)
        registration["payload"]["capabilities"] = {}
        with gateway_socket(client) as bob_socket:
            bob_socket.send_json(registration)
            assert bob_socket.receive_json()["type"] == "ack"
            (tmp_path / "node-prebound.pem").write_bytes(
                X25519PrivateKey.from_private_bytes(b"p" * 32).private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            authorize(client, alice)
            result = complete_binding(client, tmp_path, node_id="node-prebound")
            with pytest.raises(WebSocketDisconnect):
                bob_socket.receive_json()
            assert result["owner_id"] == alice.id
            row = client.app.state.connection.execute(
                "SELECT owner_id,key_id FROM node_credential_keys WHERE node_id='node-prebound'"
            ).fetchone()
            assert tuple(row) == (
                alice.id,
                registration["payload"]["credential_key_id"],
            )
            with client.websocket_connect(
                "/im/ws/gateway",
                headers={"Authorization": f"Bearer {result['runtime_token']}"},
            ) as replacement:
                replacement.send_json(registration)
                assert replacement.receive_json()["type"] == "ack"
                # A pre-transfer queued relay may never reach the new owner's node.
                assert (
                    client.portal.call(
                        lambda: client.app.state.gateway_relay.push_relay_message(
                            relay_task_id="old-owner-queued",
                            target_node_id="node-prebound",
                            payload={"metadata": {"node_epoch": 1}},
                        )
                    )
                    is False
                )
