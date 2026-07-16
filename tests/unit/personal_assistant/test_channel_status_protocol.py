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


def _register_ack() -> str:
    return json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})


def test_status_result_releases_fifo_before_terminal_handler_runs(
    tmp_path: Path,
) -> None:
    """Terminal handling observes a released slot and the next frame still flushes."""
    socket = _FakeWebSocket(
        incoming=[
            _register_ack(),
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
        await manager._listen_once()  # noqa: SLF001 - establish registration
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
            _register_ack(),
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
        await connection._listen_once()  # noqa: SLF001 - establish registration
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


def test_disconnected_runtime_replacements_coalesce_unsent_statuses(
    tmp_path: Path,
) -> None:
    """Only the current runtime incarnation survives in the disconnected queue."""
    socket = _FakeWebSocket(
        incoming=[
            _register_ack(),
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.report"}}
            ),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-0",
                        "outcome": "accepted",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-39",
                        "outcome": "accepted",
                    },
                }
            ),
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    resolved: list[str] = []

    async def handle_status(payload) -> None:
        resolved.append(str(payload["request_id"]))

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        channel_status_result_handler=handle_status,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.send_json("node.report", {"run_id": "run-1"})
        for index in range(40):
            status = _status(f"status-{index}", 1)
            status["runtime_incarnation"] = f"inc-{index}"
            await manager.send_json("channel.status", status)

        assert [frame.message_type for frame in manager._pending_frames] == [  # noqa: SLF001
            "node.report",
            "channel.status",
        ]
        assert manager._pending_frames[-1].payload["request_id"] == "status-39"  # noqa: SLF001

        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001
        await manager._listen_once()  # noqa: SLF001
        sent_statuses = [
            json.loads(frame)["payload"]
            for frame in socket.sent
            if json.loads(frame)["type"] == "channel.status"
        ]
        assert [item["request_id"] for item in sent_statuses] == ["status-39"]
        assert resolved == []
        await manager._listen_once()  # noqa: SLF001

    asyncio.run(exercise())

    sent = [json.loads(frame) for frame in socket.sent]
    assert [frame["type"] for frame in sent] == [
        "node.register",
        "node.report",
        "channel.status",
    ]
    assert sent[-1]["payload"]["runtime_incarnation"] == "inc-39"
    assert resolved == ["status-39"]


def test_retryable_manifest_is_reapplied_online_with_bounded_same_revision_retries(
    tmp_path: Path,
) -> None:
    """One inbound snapshot reports failure, retries in place, then reports applied."""
    manifest = {
        "request_id": "reconcile-2",
        "node_id": "node-a",
        "manifest_revision": 2,
        "channels": [],
        "removals": [],
    }
    socket = _FakeWebSocket(
        incoming=[
            _register_ack(),
            json.dumps({"type": "channel.reconcile", "payload": manifest}),
            json.dumps(
                {
                    "type": "channels.reconcile.result.ack",
                    "payload": {
                        "request_id": "reconcile-2",
                        "manifest_revision": 2,
                        "head_outcome": "accepted",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "channels.reconcile.result.ack",
                    "payload": {
                        "request_id": "reconcile-2:retry:1",
                        "manifest_revision": 2,
                        "head_outcome": "accepted",
                    },
                }
            ),
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    attempts = 0

    async def apply_manifest(_payload):
        nonlocal attempts
        attempts += 1
        return {
            "outcome": "applied" if attempts == 3 else "retryable_failed",
            "applied_channel_ids": [],
            "removal_outcomes": [],
            "failures": [] if attempts == 3 else [{"error_code": "cache_commit_failed"}],
        }

    async def no_wait(_delay: float) -> None:
        await asyncio.sleep(0)

    connection = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local", heartbeat_interval_seconds=0
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        channel_manifest_handler=apply_manifest,
        channel_reconcile_retry_delays=(0.1, 0.2),
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
        sleep=no_wait,
    )

    async def exercise() -> None:
        await connection.connect_once()
        await connection._listen_once()  # noqa: SLF001
        await connection._listen_once()  # noqa: SLF001
        for _ in range(20):
            if attempts == 3 and len(connection._pending_frames) == 2:  # noqa: SLF001
                break
            await asyncio.sleep(0)
        assert attempts == 3
        assert len(connection._pending_frames) == 2  # noqa: SLF001
        await connection._listen_once()  # noqa: SLF001
        await connection._listen_once()  # noqa: SLF001

    asyncio.run(exercise())

    results = [
        json.loads(frame)["payload"]
        for frame in socket.sent
        if json.loads(frame)["type"] == "channel.reconcile.result"
    ]
    assert attempts == 3
    assert [item["request_id"] for item in results] == [
        "reconcile-2",
        "reconcile-2:retry:1",
        "reconcile-2:retry:2",
    ]
    assert [item["outcome"] for item in results] == [
        "retryable_failed",
        "retryable_failed",
        "applied",
    ]
