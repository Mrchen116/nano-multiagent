"""bugfix-446-M1: connection-layer resilience for IMConnectionManager.

Covers the run_forever exception boundary (decision 2: CancelledError cleans up
then re-raises; Exception retries with backoff), the first-connect-attempt-resolved
signal that gates heartbeat startup (decision 3 guard), and the _mark_disconnected
InvalidStateError defense (decision 6).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import (
    IMConnectionConfig,
    IMConnectionManager,
    PendingFrame,
)

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


class _CancelOnRecvWebSocket(_FakeWebSocket):
    """recv raises CancelledError to simulate task cancellation mid-listen."""

    async def recv(self) -> str:
        raise asyncio.CancelledError()


class _BlockingRecvWebSocket(_FakeWebSocket):
    """recv blocks forever so the connection stays "up" without churning reconnects."""

    async def recv(self) -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")  # pragma: no cover


def _manager(
    tmp_path: Path,
    connect,
    *,
    sleep=asyncio.sleep,
) -> IMConnectionManager:
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    return IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000",
            reconnect_initial_seconds=1.0,
            reconnect_max_seconds=5.0,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=connect,
        sleep=sleep,
    )


def test_run_forever_cancelled_cleans_up_then_reraises(tmp_path: Path) -> None:
    """A CancelledError out of the listen loop must run _mark_disconnected (so the
    connection state is cleaned up) and then propagate — not be swallowed and not
    skip cleanup (issue path 5)."""
    socket = _CancelOnRecvWebSocket()
    manager = _manager(
        tmp_path, lambda url, headers: _connect_fake(socket, [], url, headers)
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(manager.run_forever())

    assert manager.connected is False
    assert any(e["event"] == "disconnected" for e in manager.event_log()), (
        "cancel must still run disconnect cleanup before re-raising"
    )


def test_run_forever_first_connect_attempt_resolves_on_success(
    tmp_path: Path,
) -> None:
    """wait_first_connect_attempt resolves once the first connect succeeds, with the
    manager actually connected — this is the signal heartbeat startup gates on."""
    socket = _BlockingRecvWebSocket()
    manager = _manager(
        tmp_path, lambda url, headers: _connect_fake(socket, [], url, headers)
    )

    async def _exercise() -> None:
        task = asyncio.create_task(manager.run_forever())
        try:
            await asyncio.wait_for(
                manager.wait_first_connect_attempt(timeout=1.0), timeout=1.0
            )
            assert manager.connected is True
        finally:
            await manager.close()
            task.cancel()
            with __import__("contextlib").suppress(asyncio.CancelledError):
                await task

    asyncio.run(_exercise())


def test_run_forever_first_connect_attempt_resolves_on_failure(
    tmp_path: Path,
) -> None:
    """Even when the first connect fails (IM unreachable at startup), the signal must
    still resolve so heartbeat startup is not blocked forever — this preserves the
    startup-order-insensitive behavior (decision 3)."""
    sleeps: list[float] = []

    async def _connect(url: str, headers: dict[str, str]):  # noqa: ARG001
        raise RuntimeError("offline")

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)
        manager._stop_requested = True  # noqa: SLF001 — stop after first backoff

    manager = _manager(tmp_path, _connect, sleep=_sleep)

    async def _exercise() -> None:
        task = asyncio.create_task(manager.run_forever())
        await asyncio.wait_for(
            manager.wait_first_connect_attempt(timeout=1.0), timeout=1.0
        )
        assert manager.connected is False
        await task

    asyncio.run(_exercise())
    assert sleeps, "a failed first connect must still enter the backoff path"


def test_wait_first_connect_attempt_is_bounded_when_connect_hangs(
    tmp_path: Path,
) -> None:
    """If the first connect hangs, wait_first_connect_attempt must return after its
    timeout cap rather than blocking heartbeat startup indefinitely (decision 3)."""
    started = asyncio.Event()

    async def _connect(url: str, headers: dict[str, str]):  # noqa: ARG001
        started.set()
        await asyncio.Event().wait()  # never resolves
        raise AssertionError("unreachable")  # pragma: no cover

    manager = _manager(tmp_path, _connect)

    async def _exercise() -> None:
        task = asyncio.create_task(manager.run_forever())
        await started.wait()
        # Must return within the cap even though connect never resolves.
        await asyncio.wait_for(
            manager.wait_first_connect_attempt(timeout=0.05), timeout=1.0
        )
        assert manager.connected is False
        manager._stop_requested = True  # noqa: SLF001
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task

    asyncio.run(_exercise())


def test_on_connected_failure_does_not_tear_down_connection(tmp_path: Path) -> None:
    """decision 3: node binding now runs inside on_connected and is non-fatal. A binding
    failure (modeled as the on_connected callback raising GatewayStartupError) must be
    swallowed — the connection stays up and the error is recorded — so a transient
    binding failure during an IM restart never kills the connection."""
    from personal_assistant.main import GatewayStartupError

    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    socket = _FakeWebSocket(incoming=[])

    async def _failing_on_connected() -> None:
        raise GatewayStartupError(
            summary="node not yet in IM bootstrap", next_step="retry on next connect"
        )

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        on_connected=_failing_on_connected,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    asyncio.run(manager.connect_once())

    assert manager.connected is True, (
        "on_connected failure must not tear down the socket"
    )
    assert any(e["event"] == "on_connected_error" for e in manager.event_log())


def test_mark_disconnected_suppresses_invalid_state_error(tmp_path: Path) -> None:
    """decision 6 (pure defense): if an ack future is concurrently resolved between the
    done() check and set_exception, _mark_disconnected must not propagate
    InvalidStateError. Simulated with a future-like whose set_exception raises."""

    class _RacyAckFuture:
        def done(self) -> bool:
            return False

        def set_exception(self, exc: BaseException) -> None:
            raise asyncio.InvalidStateError("already resolved")

    manager = _manager(
        tmp_path, lambda url, headers: _connect_fake(_FakeWebSocket(), [], url, headers)
    )
    manager._pending_frames.append(  # noqa: SLF001
        PendingFrame(
            message_type="node.report",
            payload={"run_id": "r1"},
            ack_future=_RacyAckFuture(),  # type: ignore[arg-type]
        )
    )
    manager._websocket = _FakeWebSocket()  # noqa: SLF001 — make had_connection True
    manager._connected = True  # noqa: SLF001

    # Must not raise InvalidStateError.
    manager._mark_disconnected(RuntimeError("socket dropped"))  # noqa: SLF001
    assert manager.connected is False
