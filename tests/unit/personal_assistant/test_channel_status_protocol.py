"""Channel-status result ordering tests for the Gateway IM websocket FIFO."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.base import InboundHandler, OutboundMessage
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManager,
    ChannelManifest,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


class _ManagedAdapter:
    name = "feishu:agent-a"

    def __init__(self) -> None:
        self.stopped = 0

    def start(self, _on_inbound: InboundHandler) -> None:
        pass

    def stop(self) -> None:
        self.stopped += 1

    def send(self, _outbound: OutboundMessage) -> None:
        pass


def _managed_spec() -> ManagedChannelSpec:
    return ManagedChannelSpec(
        channel_id="ch-a",
        agent_id="agent-a",
        provider="feishu",
        enabled=True,
        config={"app_id": "cli_a"},
        credentials={"app_secret": "secret"},
        provider_runtime={},
        generation=ChannelGeneration(
            provider_identity_fingerprint="fp-a",
            provider_identity_revision=1,
            channel_revision=1,
            credential_revision=1,
        ),
    )


def _status(request_id: str, sequence: int) -> dict[str, object]:
    return {
        "request_id": request_id,
        "node_id": "node-a",
        "channel_id": "ch-a",
        "channel_revision": 1,
        "runtime_incarnation": "inc-a",
        "status_sequence": sequence,
        "instance_started": sequence == 1,
        "connection_state": "connecting" if sequence == 1 else "connected",
        "diagnostics_state": "unknown",
        "checks": [],
    }


def test_status_result_releases_fifo_before_terminal_handler_runs(
    tmp_path: Path,
) -> None:
    """Terminal handling observes a released slot and the next frame still flushes."""
    socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-1",
                        "outcome": "terminal_channel_removed",
                    },
                }
            )
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    observed_pending_types: list[list[str]] = []
    manager: IMConnectionManager

    async def handle_status(_payload) -> None:
        observed_pending_types.append(
            [frame.message_type for frame in manager._pending_frames]  # noqa: SLF001
        )

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        channel_status_result_handler=handle_status,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager.send_json(
            "channel.status",
            {"request_id": "status-1", "channel_id": "ch-a"},
        )
        await manager.send_json("node.report", {"run_id": "run-1"})
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(exercise())

    assert observed_pending_types == [["node.report"]]
    assert [json.loads(frame)["type"] for frame in socket.sent] == [
        "node.register",
        "channel.status",
        "node.report",
    ]


def test_offline_barrier_removed_ack_drops_outbox_quarantines_and_continues_fifo(
    tmp_path: Path,
) -> None:
    """IM deletion of cached revision N cannot strand later reconcile/result traffic."""
    store = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json",
        node_id="node-a",
        key_id="key-a",
    )
    barrier = _status("status-1", 1)
    store.record_channel_status(barrier)
    store.record_channel_status(_status("status-2", 2))
    adapter = _ManagedAdapter()
    registry = ChannelRegistry()
    channel_manager = ChannelManager(
        registry=registry,
        on_inbound=lambda _message: None,
        provider_factories={"feishu": lambda *_args: adapter},
        status_sink=lambda _snapshot: None,
    )
    asyncio.run(
        channel_manager.reconcile(
            ChannelManifest(manifest_revision=1, channels=(_managed_spec(),))
        )
    )
    socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-1",
                        "outcome": "terminal_channel_removed",
                    },
                }
            )
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def handle_status(payload) -> None:
        ack = store.apply_channel_status_result(
            request_id=str(payload["request_id"]),
            outcome=str(payload["outcome"]),
        )
        assert ack is not None
        await channel_manager.handle_status_result(
            channel_id=ack.channel_id,
            channel_revision=ack.channel_revision,
            outcome=ack.outcome,
        )

    connection = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        channel_status_result_handler=handle_status,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await connection.connect_once()
        await connection.send_json("channel.status", barrier)
        await connection.send_json(
            "channel.reconcile.result",
            {"request_id": "reconcile-2", "manifest_revision": 2},
        )
        await connection._listen_once()  # noqa: SLF001

    asyncio.run(exercise())

    assert store.pending_channel_statuses() == ()
    assert registry.get("feishu:agent-a") is None
    assert adapter.stopped == 1
    assert [json.loads(frame)["type"] for frame in socket.sent] == [
        "node.register",
        "channel.status",
        "channel.reconcile.result",
    ]
