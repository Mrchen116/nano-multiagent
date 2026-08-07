"""Gateway websocket authentication and owner-isolation regressions."""

from __future__ import annotations

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


def _bind(client, *, node_id: str) -> None:
    started = client.post("/im/v1/bind", json={"action": "start", "node_id": node_id})
    confirmed = client.post(
        "/im/v1/bind",
        json={"action": "confirm", "bind_id": started.json()["bind_id"]},
    )
    assert confirmed.status_code == 201


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
            assert owner_socket.receive_json()["type"] == "channels.bootstrap.request"

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
        with client.websocket_connect("/im/ws/gateway") as alice_socket:
            alice_registration = _registration(node_id="node-alice", key_seed=b"a" * 32)
            alice_registration["payload"]["capabilities"] = {}
            alice_socket.send_json(alice_registration)
            assert alice_socket.receive_json()["type"] == "ack"
            _bind(client, node_id="node-alice")

            authorize(client, bob)
            with client.websocket_connect("/im/ws/gateway") as bob_socket:
                bob_registration = _registration(node_id="node-bob", key_seed=b"b" * 32)
                bob_registration["payload"]["capabilities"] = {}
                bob_socket.send_json(bob_registration)
                assert bob_socket.receive_json()["type"] == "ack"
                _bind(client, node_id="node-bob")
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
        with client.websocket_connect("/im/ws/gateway") as alice_socket:
            alice_socket.send_json(
                _registration(node_id="waiter-a", key_seed=b"c" * 32)
            )
            assert alice_socket.receive_json()["type"] == "ack"

            authorize(client, bob)
            with client.websocket_connect("/im/ws/gateway") as bob_socket:
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


def test_binding_evicts_a_pre_registered_socket_from_the_wrong_owner(
    tmp_path: Path,
) -> None:
    """Post-bind initialization must not bless the pre-bind registrant's channel key."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="bind-alice")
        bob = register_user(client, username="bind-bob")
        authorize(client, bob)
        registration = _registration(node_id="node-prebound", key_seed=b"p" * 32)
        with client.websocket_connect("/im/ws/gateway") as bob_socket:
            bob_socket.send_json(registration)
            assert bob_socket.receive_json()["type"] == "ack"

            authorize(client, alice)
            _bind(client, node_id="node-prebound")
            with pytest.raises(WebSocketDisconnect):
                bob_socket.receive_json()
            assert [node["node_id"] for node in client.get("/im/v1/nodes").json()] == [
                "node-prebound"
            ]
            assert (
                client.app.state.connection.execute(
                    "SELECT 1 FROM node_credential_keys WHERE node_id = 'node-prebound'"
                ).fetchone()
                is None
            )
