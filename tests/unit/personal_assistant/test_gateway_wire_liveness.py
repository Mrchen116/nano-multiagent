"""Wire-response and registration liveness regressions for the IM gateway."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _minimal_reporter


class _YieldingSendWebSocket(_FakeWebSocket):
    """Expose a response after transport acceptance but before ``send`` returns."""

    def __init__(self, blocked_type: str) -> None:
        super().__init__(
            incoming=[
                json.dumps(
                    {"type": "ack", "payload": {"message_type": "node.register"}}
                )
            ]
        )
        self.blocked_type = blocked_type
        self.send_started = asyncio.Event()
        self.release_send = asyncio.Event()

    async def send(self, data: str) -> None:
        self.sent.append(data)
        if json.loads(data)["type"] == self.blocked_type:
            self.send_started.set()
            await self.release_send.wait()


class _SilentWebSocket(_FakeWebSocket):
    """Accept registration but never return a protocol response."""

    async def recv(self) -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")  # pragma: no cover


def _manager(
    tmp_path: Path,
    socket: _FakeWebSocket,
    *,
    config: IMConnectionConfig | None = None,
    sleep=asyncio.sleep,
) -> IMConnectionManager:
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def connect(_url: str, _headers: dict[str, str]) -> _FakeWebSocket:
        return socket

    return IMConnectionManager(
        config=config
        or IMConnectionConfig(
            url="http://im.local", heartbeat_interval_seconds=0
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=connect,
        sleep=sleep,
    )


def test_status_result_during_yielding_send_releases_wire_owner(
    tmp_path: Path,
) -> None:
    """A server response may arrive before the local send coroutine resumes."""
    socket = _YieldingSendWebSocket("channel.status")
    manager = _manager(tmp_path, socket)
    resolved: list[str] = []

    async def handle_status(payload) -> None:
        resolved.append(str(payload["request_id"]))

    manager._channel_status_result_handler = handle_status  # noqa: SLF001

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register boundary
        send_task = asyncio.create_task(
            manager.send_json(
                "channel.status",
                {
                    "request_id": "status-early",
                    "channel_id": "channel-1",
                    "runtime_incarnation": "runtime-1",
                    "status_sequence": 1,
                },
            )
        )
        await socket.send_started.wait()
        socket.incoming.append(
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {
                        "request_id": "status-early",
                        "outcome": "accepted",
                    },
                }
            )
        )
        listen_task = asyncio.create_task(manager._listen_once())  # noqa: SLF001
        await asyncio.sleep(0)
        socket.release_send.set()
        await asyncio.wait_for(
            asyncio.gather(send_task, listen_task), timeout=0.5
        )

    asyncio.run(exercise())

    assert manager._awaiting_ack_type is None  # noqa: SLF001
    assert resolved == ["status-early"]


def test_heartbeat_ack_during_yielding_send_completes_waiter(tmp_path: Path) -> None:
    """An early heartbeat ACK cannot be consumed as an unowned no-op."""
    socket = _YieldingSendWebSocket("node.heartbeat")
    manager = _manager(tmp_path, socket)

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register boundary
        heartbeat_task = asyncio.create_task(
            manager._send_heartbeat_and_wait_ack()  # noqa: SLF001
        )
        await socket.send_started.wait()
        socket.incoming.append(
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.heartbeat"}}
            )
        )
        listen_task = asyncio.create_task(manager._listen_once())  # noqa: SLF001
        await asyncio.sleep(0)
        socket.release_send.set()
        await asyncio.wait_for(
            asyncio.gather(heartbeat_task, listen_task), timeout=0.5
        )

    asyncio.run(exercise())
    assert manager._awaiting_ack_type is None  # noqa: SLF001


def test_register_protocol_error_enters_reconnect_backoff(tmp_path: Path) -> None:
    """A rejected control frame must not reconnect in a CPU/network hot loop."""
    socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {
                    "type": "error",
                    "payload": {
                        "code": "gateway_owner_mismatch",
                        "message": "registration rejected",
                    },
                }
            )
        ]
    )
    connect_calls = 0
    sleeps: list[float] = []
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def connect(_url: str, _headers: dict[str, str]) -> _FakeWebSocket:
        nonlocal connect_calls
        connect_calls += 1
        if connect_calls > 1:
            raise RuntimeError("reconnected before backoff")
        return socket

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        manager._stop_requested = True  # noqa: SLF001

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local",
            reconnect_initial_seconds=0.25,
            reconnect_max_seconds=1.0,
            heartbeat_interval_seconds=0,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=connect,
        sleep=sleep,
    )

    asyncio.run(manager.run_forever())

    assert connect_calls == 1
    assert sleeps == [0.25]


def test_missing_register_ack_times_out_before_business_can_freeze(
    tmp_path: Path,
) -> None:
    """A live transport without register ACK must reconnect after a bounded wait."""
    socket = _SilentWebSocket()
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        manager._stop_requested = True  # noqa: SLF001

    manager = _manager(
        tmp_path,
        socket,
        config=IMConnectionConfig(
            url="http://im.local",
            reconnect_initial_seconds=0.01,
            reconnect_max_seconds=0.01,
            heartbeat_interval_seconds=0,
            registration_ack_timeout_seconds=0.01,
        ),
        sleep=sleep,
    )

    asyncio.run(manager.run_forever())

    assert socket.closed == 1
    assert sleeps == [0.01]
    assert any(
        event.get("event") == "disconnected"
        and "register ack timed out" in str(event.get("error"))
        for event in manager.event_log()
    )


def test_registration_send_shares_the_handshake_deadline(tmp_path: Path) -> None:
    """Backpressure before register send returns cannot freeze startup forever."""
    socket = _YieldingSendWebSocket("node.register")
    manager = _manager(
        tmp_path,
        socket,
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            registration_ack_timeout_seconds=0.01,
        ),
    )

    async def exercise() -> None:
        with pytest.raises(TimeoutError, match="register send timed out"):
            await asyncio.wait_for(manager.connect_once(), timeout=0.2)

    asyncio.run(exercise())
    assert manager.connected is False
    assert socket.closed == 1


def test_register_timeout_does_not_cancel_post_ack_convergence(tmp_path: Path) -> None:
    """The handshake deadline ends at ACK, before slower convergence callbacks."""
    socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.register"}}
            )
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    convergence_completed = False

    async def on_connected() -> None:
        nonlocal convergence_completed
        await asyncio.sleep(0.03)
        convergence_completed = True
        manager._stop_requested = True  # noqa: SLF001

    async def sleep(_delay: float) -> None:
        manager._stop_requested = True  # noqa: SLF001

    async def connect(_url: str, _headers: dict[str, str]) -> _FakeWebSocket:
        return socket

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            registration_ack_timeout_seconds=0.01,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        on_connected=on_connected,
        connect=connect,
        sleep=sleep,
    )

    asyncio.run(manager.run_forever())

    assert convergence_completed is True
    assert manager.connected is True
    assert not any(
        "register ack timed out" in str(event.get("error"))
        for event in manager.event_log()
    )
