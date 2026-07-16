"""Regression coverage for heartbeat admission during IM reconnect setup."""

from __future__ import annotations

import asyncio

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


def test_slow_on_connected_does_not_start_heartbeat_before_receive_loop(
    tmp_path,
) -> None:
    """A buffered register ack cannot be consumed while on_connected owns connect_once."""

    register_ack = '{"type":"ack","payload":{"message_type":"node.register"}}'
    socket = _FakeWebSocket([register_ack])
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    release_callback = asyncio.Event()
    callback_started = asyncio.Event()

    async def _on_connected() -> None:
        callback_started.set()
        await release_callback.wait()

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000",
            reconnect_initial_seconds=0.01,
            reconnect_max_seconds=0.01,
            heartbeat_interval_seconds=0.01,
            heartbeat_ack_timeout_seconds=0.01,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
        on_connected=_on_connected,
    )

    async def _exercise() -> None:
        task = asyncio.create_task(manager.connect_once())
        await callback_started.wait()
        await asyncio.sleep(0.05)
        try:
            assert manager.connected is True
            assert all("node.heartbeat" not in frame for frame in socket.sent)
        finally:
            release_callback.set()
            await task
            await manager.close()

    asyncio.run(_exercise())
