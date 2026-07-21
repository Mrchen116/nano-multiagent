"""Legacy channel bootstrap across manual bind and the Gateway websocket."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.channel_credentials import (
    ChannelEnvelopeAad,
    generate_channel_key_pair,
    seal_channel_secret,
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
)


def test_manual_bind_bootstraps_once_on_same_websocket_then_replays_manifest(
    tmp_path: Path,
) -> None:
    """Bind confirmation initializes legacy desired state without reconnecting."""
    app = create_app(db_path=tmp_path / "im.db")
    key = generate_channel_key_pair(private_seed=b"b" * 32)
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        authorize(client, owner)
        with client.websocket_connect("/im/ws/gateway") as websocket:
            websocket.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node-bootstrap",
                        "node_name": "Bootstrap Node",
                        "agents": ["agent-a"],
                        "capabilities": {
                            "relay": True,
                            "channel_bootstrap": True,
                        },
                        "credential_key_id": key.key_id,
                        "credential_algorithm": "X25519-HKDF-SHA256-AES-256-GCM",
                        "credential_public_key": key.public_key,
                    },
                }
            )
            assert websocket.receive_json()["type"] == "ack"

            started = client.post(
                "/im/v1/bind",
                json={"action": "start", "node_id": "node-bootstrap"},
            )
            confirmed = client.post(
                "/im/v1/bind",
                json={"action": "confirm", "bind_id": started.json()["bind_id"]},
            )
            assert confirmed.status_code == 201
            request = websocket.receive_json()
            assert request["type"] == "channels.bootstrap.request"
            request_id = request["payload"]["request_id"]

            channel_id = "ch-legacy-a"
            envelope = seal_channel_secret(
                public_key=key.public_key,
                secret={"app_secret": "legacy-secret"},
                aad=ChannelEnvelopeAad(
                    owner_id=owner.owner_id,
                    node_id="node-bootstrap",
                    agent_id="agent-a",
                    channel_id=channel_id,
                    provider="feishu",
                    credential_revision=1,
                ),
            )
            websocket.send_json(
                {
                    "type": "channels.bootstrap",
                    "payload": {
                        "request_id": request_id,
                        "node_id": "node-bootstrap",
                        "items": [
                            {
                                "channel_id": channel_id,
                                "agent_id": "agent-a",
                                "provider": "feishu",
                                "enabled": True,
                                "config": {"app_id": "cli_legacy"},
                                "credential_envelope": envelope,
                                "credential_key_id": key.key_id,
                                "credential_revision": 1,
                                "provider_runtime": {"owner_open_id": "ou-owner"},
                            }
                        ],
                    },
                }
            )
            result = websocket.receive_json()
            assert result["type"] == "channels.bootstrap.result"
            assert result["payload"]["outcome"] == "initialized"
            manifest = result["payload"]["manifest"]
            assert manifest["manifest_revision"] == 1
            assert manifest["channels"][0]["channel_id"] == channel_id
            assert "legacy-secret" not in str(result)

            repeated = client.post(
                "/im/v1/bind",
                json={"action": "confirm", "bind_id": started.json()["bind_id"]},
            )
            assert repeated.status_code == 201
            replay = websocket.receive_json()
            assert replay["type"] == "channel.reconcile"
            assert replay["payload"]["manifest_revision"] == 1

        listed = client.get("/im/v1/agents/agent-a/channels")
        assert listed.status_code == 200
        assert [item["channel_id"] for item in listed.json()] == [channel_id]


def test_gateway_bootstrap_response_is_empty_without_legacy_yaml_bridge(
    tmp_path: Path,
) -> None:
    """The current bootstrap handshake never imports local channel secrets."""
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "channels.bootstrap.request",
                    "payload": {
                        "request_id": "bootstrap-1",
                        "node_id": "node-a",
                        "owner_id": "owner-a",
                    },
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
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()
        await manager._listen_once()

    asyncio.run(exercise())

    sent = [json.loads(frame) for frame in socket.sent]
    bootstrap = next(frame for frame in sent if frame["type"] == "channels.bootstrap")
    assert bootstrap["payload"] == {
        "request_id": "bootstrap-1",
        "node_id": "node-a",
        "items": [],
    }
