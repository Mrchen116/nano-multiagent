"""Wire-response and registration liveness regressions for the IM gateway."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import (
    _FakeWebSocket,
    _managed_channel_bindings,
    _minimal_reporter,
)


def test_business_ack_default_allows_remote_im_round_trips() -> None:
    config = IMConnectionConfig(url="http://im.example")

    assert config.business_ack_timeout_seconds == 10.0


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
        or IMConnectionConfig(url="http://im.local", heartbeat_interval_seconds=0),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=connect,
        sleep=sleep,
    )


def test_business_send_timeout_disconnects_half_open_socket(tmp_path: Path) -> None:
    socket = _YieldingSendWebSocket("node.streaming_delta")
    manager = _manager(
        tmp_path,
        socket,
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            business_ack_timeout_seconds=0.01,
        ),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register boundary
        await asyncio.wait_for(
            manager.send_json("node.streaming_delta", {"kind": "message_delta"}),
            timeout=0.2,
        )

    asyncio.run(exercise())

    assert manager.connected is False
    assert socket.closed == 1


def test_business_ack_timeout_disconnects_silent_socket(tmp_path: Path) -> None:
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    manager = _manager(
        tmp_path,
        socket,
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            business_ack_timeout_seconds=0.01,
        ),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register boundary
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(
                manager.send_json_await_ack(
                    "node.streaming_delta", {"kind": "turn_start"}
                ),
                timeout=0.2,
            )

    asyncio.run(exercise())

    assert manager.connected is False
    assert socket.closed == 1


def test_queued_waiter_ack_budget_starts_only_after_it_owns_wire(
    tmp_path: Path,
) -> None:
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    manager = _manager(
        tmp_path,
        socket,
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            business_ack_timeout_seconds=0.01,
        ),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register boundary
        await manager.send_json("node.report", {"run_id": "owner"})
        waiter = asyncio.create_task(
            manager.send_json_await_ack("agent.message", {"text": "queued"})
        )
        await asyncio.sleep(0)
        assert manager.connected is True
        assert waiter.done() is False

        socket.incoming.append(
            json.dumps({"type": "ack", "payload": {"message_type": "node.report"}})
        )
        await manager._listen_once()  # noqa: SLF001 - release first wire owner
        socket.incoming.append(
            json.dumps({"type": "ack", "payload": {"message_type": "agent.message"}})
        )
        await manager._listen_once()  # noqa: SLF001 - acknowledge queued waiter
        await waiter

    asyncio.run(exercise())


def test_fire_and_forget_business_frame_has_its_own_ack_timeout(
    tmp_path: Path,
) -> None:
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    manager = _manager(
        tmp_path,
        socket,
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            business_ack_timeout_seconds=0.01,
        ),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register boundary
        await manager.send_json("node.report", {"run_id": "fire-and-forget"})
        await asyncio.sleep(0.03)

    asyncio.run(exercise())

    assert manager.connected is False
    assert socket.closed == 1
    assert any(
        event.get("event") == "disconnected"
        and "node.report ack timed out" in str(event.get("error"))
        for event in manager.event_log()
    )


def test_external_shadow_live_frame_is_not_replayed_after_send_timeout(
    tmp_path: Path,
) -> None:
    first_socket = _YieldingSendWebSocket("node.streaming_delta")
    first_socket.blocked_type = "never-block-turn-start"
    second_socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    sockets = iter((first_socket, second_socket))
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def connect(_url: str, _headers: dict[str, str]) -> _FakeWebSocket:
        return next(sockets)

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local",
            heartbeat_interval_seconds=0,
            business_ack_timeout_seconds=0.01,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=connect,
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - first register boundary
        turn_start = asyncio.create_task(
            manager.send_json_await_ack(
                "node.streaming_delta",
                {
                    "kind": "turn_start",
                    "run_id": "external-run",
                    "conversation_id": "conversation-1",
                    "agent_id": "agent-1",
                    "shadow_message_id": "shadow-message-1",
                },
            )
        )
        await asyncio.sleep(0)
        first_socket.incoming.append(
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.streaming_delta"}}
            )
        )
        await manager._listen_once()  # noqa: SLF001 - turn_start ACK
        await turn_start

        first_socket.blocked_type = "node.streaming_delta"
        await manager.send_json(
            "node.streaming_delta",
            {
                "kind": "message_delta",
                "run_id": "external-run",
                "message_id": "im-message-1",
                "delta_text": "stale",
            },
        )
        assert manager.connected is False
        assert list(manager._pending_frames) == []  # noqa: SLF001

        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - second register boundary

    asyncio.run(exercise())

    second_types = [json.loads(frame)["type"] for frame in second_socket.sent]
    assert second_types == ["node.register"]


def test_status_result_during_yielding_send_releases_wire_owner(
    tmp_path: Path,
) -> None:
    """A server response may arrive before the local send coroutine resumes."""
    socket = _YieldingSendWebSocket("channel.status")
    resolved: list[str] = []

    async def handle_status(payload) -> None:
        resolved.append(str(payload["request_id"]))

    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def connect(_url: str, _headers: dict[str, str]) -> _FakeWebSocket:
        return socket

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local", heartbeat_interval_seconds=0),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        managed_channel_bindings=_managed_channel_bindings(
            handle_status_result=handle_status
        ),
        connect=connect,
    )

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
        await asyncio.wait_for(asyncio.gather(send_task, listen_task), timeout=0.5)

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
            json.dumps({"type": "ack", "payload": {"message_type": "node.heartbeat"}})
        )
        listen_task = asyncio.create_task(manager._listen_once())  # noqa: SLF001
        await asyncio.sleep(0)
        socket.release_send.set()
        await asyncio.wait_for(asyncio.gather(heartbeat_task, listen_task), timeout=0.5)

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
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}})
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    convergence_completed = False

    async def on_connected(_sender: object) -> None:
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
