"""Channel-status result ordering tests for the Gateway IM websocket FIFO."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


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

