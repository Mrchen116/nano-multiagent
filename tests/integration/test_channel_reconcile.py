"""Cross-boundary tests for online channel key registration and reconciliation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import stat
import threading

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.channel_credentials import ChannelEnvelopeAad, seal_channel_secret
from IM.infra.repositories import AgentProfileRepository, NodeRepository
from personal_assistant.channels.channel_credentials import (
    GatewayChannelAad,
    GatewayChannelKeyStore,
)
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import NodeConfig
from personal_assistant.reporter.upstream_reporter import UpstreamReporter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager
from tests.im_service._auth_helpers import authorize, register_user
from tests.unit.personal_assistant._im_connection_helpers import (
    _FakeWebSocket,
    _agents,
    _connect_fake,
    _managed_channel_bindings,
)


def _seed_agent(client: TestClient, *, owner_id: str) -> None:
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
        skills=["planning"],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )


def test_gateway_key_file_opens_im_envelope_and_registers_public_only(
    tmp_path: Path,
) -> None:
    """The stable 0600 private key never crosses node.register or the IM boundary."""
    key_path = tmp_path / "channel-credentials-v1.pem"
    key = GatewayChannelKeyStore(key_path).load_or_create()
    reloaded = GatewayChannelKeyStore(key_path).load_or_create()
    aad = GatewayChannelAad(
        owner_id="owner-a",
        node_id="node-a",
        agent_id="agent-a",
        channel_id="ch-a",
        provider="feishu",
        credential_revision=1,
    )
    envelope = seal_channel_secret(
        public_key=key.public_key,
        secret={"app_secret": "cross-boundary-secret"},
        aad=ChannelEnvelopeAad(**aad.as_dict()),
    )
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-a"),
        agents=(),
        send_frame=lambda _kind, _payload: None,
        channel_credential_key=key.registration_payload(),
    )

    assert reloaded.key_id == key.key_id
    assert reloaded.open(envelope=envelope, aad=aad) == {
        "app_secret": "cross-boundary-secret"
    }
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    registration = reporter.send_register()
    assert registration["credential_key_id"] == key.key_id
    assert registration["credential_algorithm"] == key.algorithm
    assert registration["credential_public_key"] == key.public_key
    assert key.private_key_pem not in json.dumps(registration)


def test_online_http_save_pushes_manifest_and_status_projects_connected(
    tmp_path: Path,
) -> None:
    """A real HTTP save reaches the connected node and becomes applied without restart."""
    key = GatewayChannelKeyStore(
        tmp_path / "channel-credentials-v1.pem"
    ).load_or_create()
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        _seed_agent(client, owner_id=owner.owner_id)

        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-a",
                        "node_name": "Node A",
                        "agents": ["agent-a"],
                        "capabilities": {"relay": True},
                        **key.registration_payload(),
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            result: dict[str, object] = {}

            def create_channel() -> None:
                result["response"] = client.post(
                    "/im/v1/agents/agent-a/channels",
                    json={
                        "provider": "feishu",
                        "config": {"app_id": "cli_online"},
                        "credentials": {
                            "mode": "replace",
                            "app_secret": "online-secret",
                        },
                    },
                )

            worker = threading.Thread(target=create_channel)
            worker.start()
            reconcile = websocket.receive_json()
            assert reconcile["type"] == "channel.reconcile"
            payload = reconcile["payload"]
            assert payload["node_id"] == "node-a"
            assert payload["manifest_revision"] == 1
            assert len(payload["channels"]) == 1
            assert "online-secret" not in json.dumps(reconcile)
            channel = payload["channels"][0]
            channel_id = channel["channel_id"]
            worker.join(timeout=5)
            response = result["response"]
            assert response.status_code == 201

            websocket.send_json(
                {
                    "type": "channel.reconcile.result",
                    "payload": {
                        "request_id": payload["request_id"],
                        "node_id": "node-a",
                        "manifest_revision": 1,
                        "outcomes": [{"channel_id": channel_id, "outcome": "applied"}],
                    },
                }
            )
            assert websocket.receive_json()["payload"]["message_type"] == (
                "channel.reconcile.result"
            )
            websocket.send_json(
                {
                    "type": "channel.status",
                    "payload": {
                        "request_id": "status-1",
                        "node_id": "node-a",
                        "channel_id": channel_id,
                        "channel_revision": 1,
                        "runtime_incarnation": "inc-a",
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
                "payload": {"request_id": "status-1", "outcome": "accepted"},
            }

            listed = client.get("/im/v1/agents/agent-a/channels").json()[0]
            assert listed["sync_state"] == "applied"
            assert listed["observed"]["connection_state"] == "connected"
            assert listed["observed"]["status_updated_at"]

            generation = {
                key: channel[key]
                for key in (
                    "provider_identity_fingerprint",
                    "provider_identity_revision",
                    "channel_revision",
                    "credential_revision",
                )
            }
            websocket.send_json(
                {
                    "type": "channel.runtime_metadata",
                    "payload": {
                        "request_id": "metadata-1",
                        "node_id": "node-a",
                        "channel_id": channel_id,
                        "provider_runtime_patch": {"owner_open_id": "ou_first"},
                        **generation,
                    },
                }
            )
            assert websocket.receive_json()["payload"]["outcome"] == "accepted"
            websocket.send_json(
                {
                    "type": "channel.runtime_metadata",
                    "payload": {
                        "request_id": "metadata-2",
                        "node_id": "node-a",
                        "channel_id": channel_id,
                        "provider_runtime_patch": {"owner_open_id": "ou_second"},
                        **generation,
                    },
                }
            )
            assert websocket.receive_json()["payload"]["outcome"] == "already_current"

            replacement_result: dict[str, object] = {}

            def replace_app() -> None:
                replacement_result["response"] = client.patch(
                    f"/im/v1/agents/agent-a/channels/{channel_id}",
                    json={
                        "channel_revision": 1,
                        "enabled": True,
                        "config": {"app_id": "cli_replacement"},
                        "credentials": {
                            "mode": "replace",
                            "app_secret": "replacement-secret",
                        },
                    },
                )

            replacement_worker = threading.Thread(target=replace_app)
            replacement_worker.start()
            replacement_manifest = websocket.receive_json()
            replacement_worker.join(timeout=5)
            assert replacement_result["response"].status_code == 200
            replacement_channel = replacement_manifest["payload"]["channels"][0]
            assert replacement_channel["provider_runtime"] == {}
            websocket.send_json(
                {
                    "type": "channel.runtime_metadata",
                    "payload": {
                        "request_id": "metadata-stale",
                        "node_id": "node-a",
                        "channel_id": channel_id,
                        "provider_runtime_patch": {"owner_open_id": "ou_stale"},
                        **generation,
                    },
                }
            )
            assert websocket.receive_json()["payload"]["outcome"] == (
                "terminal_stale_revision"
            )


def test_gateway_dispatches_manifest_and_correlated_result_releases_fifo(
    tmp_path: Path,
) -> None:
    """Reconcile and status result frames coexist with the existing single-slot FIFO."""
    handled: list[dict[str, object]] = []

    async def apply_manifest(payload):
        handled.append(dict(payload))
        return {"outcomes": [{"channel_id": "ch-a", "outcome": "applied"}]}

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "channel.reconcile",
                    "payload": {
                        "request_id": "reconcile-1",
                        "node_id": "node-a",
                        "manifest_revision": 4,
                        "channels": [],
                        "removals": [],
                    },
                }
            ),
            json.dumps(
                {
                    "type": "ack",
                    "payload": {"message_type": "channel.reconcile.result"},
                }
            ),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {"request_id": "status-1", "outcome": "accepted"},
                }
            ),
        ]
    )
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-a"),
        agents=_agents(tmp_path),
        send_frame=lambda _kind, _payload: None,
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local"),
        reporter=reporter,
        relay_adapter=relay,
        managed_channel_bindings=_managed_channel_bindings(
            apply_manifest=apply_manifest
        ),
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()
        await manager._listen_once()
        await manager._listen_once()
        await manager.send_json(
            "channel.status",
            {
                "request_id": "status-1",
                "node_id": "node-a",
                "channel_id": "ch-a",
            },
        )
        await manager.send_json(
            "channel.runtime_metadata",
            {"request_id": "metadata-1", "node_id": "node-a", "channel_id": "ch-a"},
        )
        await manager._listen_once()

    asyncio.run(exercise())

    assert handled[0]["manifest_revision"] == 4
    sent = [json.loads(frame) for frame in socket.sent]
    assert [frame["type"] for frame in sent][-3:] == [
        "channel.reconcile.result",
        "channel.status",
        "channel.runtime_metadata",
    ]
