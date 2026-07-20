"""Behavioral ownership tests for Gateway channel-status wire delivery."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.gateway.managed_channel_control import (
    ChannelStatusDirective,
    ManagedChannelBindings,
    ManagedChannelEmissionSource,
)
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


def _status(request_id: str, *, incarnation: str, sequence: int) -> dict[str, object]:
    return {
        "request_id": request_id,
        "channel_id": "ch-a",
        "channel_revision": 1,
        "runtime_incarnation": incarnation,
        "status_sequence": sequence,
        "instance_started": sequence == 1,
        "connection_state": "connecting" if sequence == 1 else "connected",
        "diagnostics_state": "unknown",
        "checks": [],
    }


class _YieldingStatusWebSocket(_FakeWebSocket):
    """Pause one status write after transport ownership should be established."""

    def __init__(self) -> None:
        super().__init__(
            incoming=[
                json.dumps(
                    {"type": "ack", "payload": {"message_type": "node.register"}}
                )
            ]
        )
        self.status_send_started = asyncio.Event()
        self.release_status_send = asyncio.Event()

    async def send(self, data: str) -> None:
        frame = json.loads(data)
        if (
            frame["type"] == "channel.status"
            and frame["payload"]["request_id"] == "status-old"
        ):
            self.status_send_started.set()
            await self.release_status_send.wait()
        await super().send(data)


def test_status_coalescing_cannot_remove_frame_after_wire_send_begins(
    tmp_path: Path,
) -> None:
    """A status queued during an awaited send cannot steal the in-flight result."""
    socket = _YieldingStatusWebSocket()
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
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - establish registered boundary

        old_send = asyncio.create_task(
            manager.send_json(
                "channel.status",
                _status("status-old", incarnation="inc-a", sequence=2),
            )
        )
        await socket.status_send_started.wait()
        new_send = asyncio.create_task(
            manager.send_json(
                "channel.status",
                _status("status-new", incarnation="inc-a", sequence=3),
            )
        )
        await asyncio.sleep(0)
        socket.release_status_send.set()
        await asyncio.gather(old_send, new_send)

        socket.incoming.extend(
            [
                json.dumps(
                    {
                        "type": "channel.status.result",
                        "payload": {
                            "request_id": "status-old",
                            "outcome": "accepted",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "channel.status.result",
                        "payload": {
                            "request_id": "status-new",
                            "outcome": "accepted",
                        },
                    }
                ),
            ]
        )
        await manager._listen_once()  # noqa: SLF001 - old result releases only old
        await manager._listen_once()  # noqa: SLF001 - new result releases only new

    asyncio.run(exercise())

    status_request_ids = [
        json.loads(frame)["payload"]["request_id"]
        for frame in socket.sent
        if json.loads(frame)["type"] == "channel.status"
    ]
    assert status_request_ids == ["status-old", "status-new"]
    assert resolved == ["status-old", "status-new"]


def test_fatal_status_directive_closes_before_later_business_frame_flushes(
    tmp_path: Path,
) -> None:
    """A fatal status result closes in the receive stack before FIFO advances."""
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-fatal",
                        "outcome": "fatal_owner_mismatch",
                    },
                }
            ),
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def apply_manifest(_payload: dict[str, object]) -> dict[str, object]:
        return {}

    async def reconnect(_channel_id: str, _revision: int) -> None:
        return None

    async def handle_status(_payload: dict[str, object]) -> ChannelStatusDirective:
        return ChannelStatusDirective.CLOSE_CONNECTION

    async def reconcile_after_register() -> None:
        return None

    bindings = ManagedChannelBindings(
        apply_manifest=apply_manifest,
        reconnect=reconnect,
        acknowledge_reconcile=lambda _payload: None,
        handle_status_result=handle_status,
        reconcile_after_register=reconcile_after_register,
        emissions=ManagedChannelEmissionSource(),
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        managed_channel_bindings=bindings,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - establish registration
        await manager.send_json(
            "channel.status",
            _status("status-fatal", incarnation="inc-a", sequence=2),
        )
        await manager.send_json("node.report", {"status": "healthy"})
        await manager._listen_once()  # noqa: SLF001 - consume fatal result

    asyncio.run(exercise())

    assert socket.closed == 1
    assert [json.loads(frame)["type"] for frame in socket.sent] == [
        "node.register",
        "channel.status",
    ]


def test_new_incarnation_supersedes_disconnected_unacked_status_on_next_socket(
    tmp_path: Path,
) -> None:
    """Reconnect replays only the current runtime status and preserves other FIFO."""
    first_socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    second_socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {"request_id": "status-old", "outcome": "accepted"},
                }
            ),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-current",
                        "outcome": "accepted",
                    },
                }
            ),
            json.dumps({"type": "ack", "payload": {"message_type": "node.report"}}),
        ]
    )
    sockets = [first_socket, second_socket]
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    resolved: list[str] = []

    async def connect(url, headers):
        return await _connect_fake(sockets.pop(0), [], url, headers)

    async def handle_status(payload) -> None:
        resolved.append(str(payload["request_id"]))

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        channel_status_result_handler=handle_status,
        connect=connect,
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register socket one
        await manager.send_json(
            "channel.status",
            _status("status-old", incarnation="inc-old", sequence=2),
        )
        await manager._disconnect_current_websocket(  # noqa: SLF001
            RuntimeError("socket one dropped before result")
        )
        await manager.send_json(
            "channel.status",
            _status("status-current", incarnation="inc-current", sequence=1),
        )
        await manager.send_json("node.report", {"status": "healthy"})

        await manager.connect_once()
        assert [json.loads(frame)["type"] for frame in second_socket.sent] == [
            "node.register"
        ]
        await manager._listen_once()  # noqa: SLF001 - register ack flushes current
        await manager._listen_once()  # noqa: SLF001 - late old result is a no-op
        await manager._listen_once()  # noqa: SLF001 - current result releases current
        await manager._listen_once()  # noqa: SLF001 - report ack drains FIFO

    asyncio.run(exercise())

    first_statuses = [
        json.loads(frame)["payload"]
        for frame in first_socket.sent
        if json.loads(frame)["type"] == "channel.status"
    ]
    second_frames = [json.loads(frame) for frame in second_socket.sent]
    second_statuses = [
        frame["payload"] for frame in second_frames if frame["type"] == "channel.status"
    ]
    assert [item["runtime_incarnation"] for item in first_statuses] == ["inc-old"]
    assert [item["runtime_incarnation"] for item in second_statuses] == ["inc-current"]
    assert [frame["type"] for frame in second_frames] == [
        "node.register",
        "channel.status",
        "node.report",
    ]
    assert resolved == ["status-current"]
