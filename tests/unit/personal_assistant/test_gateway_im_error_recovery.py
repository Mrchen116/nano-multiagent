"""Rejected IM frame ownership and outbound queue recovery."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import (
    IMConnectionConfig,
    IMConnectionManager,
    IMFrameRejectedError,
)

from .test_gateway_im_connection_behavior import (
    _FakeWebSocket,
    _connect_fake,
    _minimal_reporter,
)


def test_rejected_agent_message_fails_waiter_and_flushes_next_frame(
    tmp_path: Path,
) -> None:
    """An invalid send_message cannot poison all later Gateway visibility frames."""

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "error",
                    "payload": {
                        "message_type": "agent.message",
                        "code": "invalid_agent_message",
                        "message": "target conversation is not visible",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "ack",
                    "payload": {
                        "message_type": "node.report",
                        "run_id": "run-next",
                    },
                }
            ),
        ]
    )
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local:9000"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def _exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - registration ack
        invalid = asyncio.create_task(
            manager.send_agent_message(
                {
                    "from_session_id": "agent-a|tool_call:bad",
                    "to": "conversation:missing",
                    "text": "not delivered",
                }
            )
        )
        await asyncio.sleep(0)
        following = asyncio.create_task(
            manager.send_json_await_ack("node.report", {"run_id": "run-next"})
        )
        await asyncio.sleep(0)

        await manager._listen_once()  # noqa: SLF001 - correlated error
        with pytest.raises(
            IMFrameRejectedError,
            match="agent.message.*invalid_agent_message.*target conversation",
        ):
            await invalid
        assert manager.connected is True
        assert manager._awaiting_ack_type == "node.report"  # noqa: SLF001

        await manager._listen_once()  # noqa: SLF001 - following ack
        assert await following == {
            "message_type": "node.report",
            "run_id": "run-next",
        }
        assert list(manager._pending_frames) == []  # noqa: SLF001

    asyncio.run(_exercise())
