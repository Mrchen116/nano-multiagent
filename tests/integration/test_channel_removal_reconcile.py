"""Cross-boundary lifecycle tests for reconnect and explicit removal results."""

from __future__ import annotations

from pathlib import Path
import threading

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.channel_credentials import generate_channel_key_pair
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.nodes import NodeRepository
from tests.im_service._auth_helpers import authorize, register_user


def _seed_agent(client: TestClient, *, owner_id: str) -> dict[str, str]:
    NodeRepository(client.app.state.connection).upsert_node(
        node_id="node-a",
        node_name="Node A",
        owner_id=owner_id,
        status="online",
    )
    AgentProfileRepository(client.app.state.connection).upsert_profile(
        agent_id="agent-a",
        owner_id=owner_id,
        node_id="node-a",
        display_name="Agent A",
        description="",
        system_prompt="You are Agent A.",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    pair = generate_channel_key_pair(private_seed=b"r" * 32)
    return {
        "credential_key_id": pair.key_id,
        "credential_algorithm": "X25519-HKDF-SHA256-AES-256-GCM",
        "credential_public_key": pair.public_key,
    }


def test_connected_reconnect_and_failed_removal_retry_use_same_manifest_revision(
    tmp_path: Path,
) -> None:
    """The real HTTP/WS entry keeps deletion visible until a successful apply result."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app, raise_server_exceptions=False) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        registration = _seed_agent(client, owner_id=owner.owner_id)

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-a",
                        "node_name": "Node A",
                        "agents": ["agent-a"],
                        "capabilities": {"relay": True},
                        **registration,
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            create_result: dict[str, object] = {}

            def create() -> None:
                create_result["response"] = client.post(
                    "/im/v1/agents/agent-a/channels",
                    json={
                        "provider": "feishu",
                        "config": {"app_id": "cli_lifecycle"},
                        "credentials": {
                            "mode": "replace",
                            "app_secret": "lifecycle-secret",
                        },
                    },
                )

            create_thread = threading.Thread(target=create)
            create_thread.start()
            create_manifest = websocket.receive_json()
            create_thread.join(timeout=5)
            created_response = create_result["response"]
            assert created_response.status_code == 201
            channel_id = created_response.json()["channel_id"]
            create_request_id = create_manifest["payload"]["request_id"]
            websocket.send_json(
                {
                    "type": "channel.reconcile.result",
                    "payload": {
                        "request_id": create_request_id,
                        "node_id": "node-a",
                        "manifest_revision": 1,
                        "outcome": "applied",
                        "applied_channel_ids": [channel_id],
                        "removal_outcomes": [],
                        "failures": [],
                    },
                }
            )
            create_ack = websocket.receive_json()
            assert create_ack["type"] == "channels.reconcile.result.ack"
            assert create_ack["payload"]["head_outcome"] == "accepted"
            websocket.send_json(
                {
                    "type": "channel.status",
                    "payload": {
                        "request_id": "status-connected",
                        "node_id": "node-a",
                        "channel_id": channel_id,
                        "channel_revision": 1,
                        "runtime_incarnation": "inc-connected",
                        "status_sequence": 1,
                        "instance_started": True,
                        "connection_state": "connected",
                        "diagnostics_state": "complete",
                        "checks": [],
                    },
                }
            )
            status_result = websocket.receive_json()
            assert status_result == {
                "type": "channel.status.result",
                "payload": {
                    "request_id": "status-connected",
                    "outcome": "accepted",
                },
            }

            reconnect_result: dict[str, object] = {}

            def reconnect() -> None:
                reconnect_result["response"] = client.post(
                    f"/im/v1/agents/agent-a/channels/{channel_id}/actions/reconnect"
                )

            reconnect_thread = threading.Thread(target=reconnect)
            reconnect_thread.start()
            reconnect_thread.join(timeout=5)
            assert reconnect_thread.is_alive() is False
            assert reconnect_result["response"].status_code == 200
            reconnect_frame = websocket.receive_json()
            assert reconnect_frame == {
                "type": "channel.reconnect",
                "payload": {"channel_id": channel_id, "channel_revision": 1},
            }

            delete_result: dict[str, object] = {}

            def delete() -> None:
                delete_result["response"] = client.delete(
                    f"/im/v1/agents/agent-a/channels/{channel_id}?channel_revision=1"
                )

            delete_thread = threading.Thread(target=delete)
            delete_thread.start()
            delete_manifest = websocket.receive_json()
            delete_thread.join(timeout=5)
            assert delete_result["response"].status_code == 200
            assert delete_manifest["payload"]["manifest_revision"] == 2
            assert delete_manifest["payload"]["channels"] == []
            intent = delete_manifest["payload"]["removals"][0]

            websocket.send_json(
                {
                    "type": "channel.reconcile.result",
                    "payload": {
                        "request_id": delete_manifest["payload"]["request_id"],
                        "node_id": "node-a",
                        "manifest_revision": 2,
                        "outcome": "retryable_failed",
                        "applied_channel_ids": [],
                        "removal_outcomes": [
                            {
                                **intent,
                                "outcome": "failed",
                                "error_code": "runtime_stop_failed",
                                "error_message": "worker exit timed out",
                            }
                        ],
                        "failures": [],
                    },
                }
            )
            failed_ack = websocket.receive_json()
            assert failed_ack["type"] == "channels.reconcile.result.ack"
            failed_view = client.get("/im/v1/agents/agent-a/channels").json()[0]
            assert failed_view["apply_state"] == "failed"

            retry_result: dict[str, object] = {}

            def retry() -> None:
                retry_result["response"] = client.post(
                    f"/im/v1/agents/agent-a/channel-removals/{channel_id}/actions/retry"
                )

            retry_thread = threading.Thread(target=retry)
            retry_thread.start()
            retry_manifest = websocket.receive_json()
            retry_thread.join(timeout=5)
            assert retry_result["response"].status_code == 200
            assert retry_manifest["payload"]["manifest_revision"] == 2
            websocket.send_json(
                {
                    "type": "channel.reconcile.result",
                    "payload": {
                        "request_id": retry_manifest["payload"]["request_id"],
                        "node_id": "node-a",
                        "manifest_revision": 2,
                        "outcome": "applied",
                        "applied_channel_ids": [],
                        "removal_outcomes": [{**intent, "outcome": "applied"}],
                        "failures": [],
                    },
                }
            )
            applied_ack = websocket.receive_json()
            assert (
                applied_ack["payload"]["removal_token_outcomes"][0]["outcome"]
                == "accepted"
            )
            assert client.get("/im/v1/agents/agent-a/channels").json() == []
