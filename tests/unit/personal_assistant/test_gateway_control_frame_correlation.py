"""Register and heartbeat correlation boundaries for Gateway upstream traffic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
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


def test_register_error_never_rejects_buffered_business_fifo(tmp_path: Path) -> None:
    """A failed register leaves report, status, message, and waiter for reconnect."""
    first_socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {
                    "type": "error",
                    "payload": {
                        "code": "gateway_owner_mismatch",
                        "message": "registered owner does not match token owner",
                    },
                }
            )
        ]
    )
    second_socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.register"}}
            ),
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.report"}}
            ),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {"request_id": "status-1", "outcome": "accepted"},
                }
            ),
            json.dumps(
                {
                    "type": "ack",
                    "payload": {
                        "message_type": "agent.message",
                        "conversation_id": "conv-1",
                    },
                }
            ),
        ]
    )
    sockets = [first_socket, second_socket]
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)

    async def connect(url, headers):
        return await _connect_fake(sockets.pop(0), [], url, headers)

    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local", heartbeat_interval_seconds=0),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=connect,
    )

    async def exercise() -> None:
        await manager.send_json("node.report", {"status": "healthy"})
        await manager.send_json(
            "channel.status",
            _status("status-1", incarnation="inc-a", sequence=1),
        )
        waiter = asyncio.create_task(
            manager.send_json_await_ack("agent.message", {"text": "hello"})
        )
        await asyncio.sleep(0)

        await manager.connect_once()
        assert [json.loads(frame)["type"] for frame in first_socket.sent] == [
            "node.register"
        ]
        await manager._listen_once()  # noqa: SLF001 - register owner mismatch
        assert not waiter.done()

        await manager.connect_once()
        assert [json.loads(frame)["type"] for frame in second_socket.sent] == [
            "node.register"
        ]
        for _ in range(4):
            await manager._listen_once()  # noqa: SLF001 - drive registered FIFO
        assert await waiter == {
            "message_type": "agent.message",
            "conversation_id": "conv-1",
        }

    asyncio.run(exercise())

    assert [json.loads(frame)["type"] for frame in second_socket.sent] == [
        "node.register",
        "node.report",
        "channel.status",
        "agent.message",
    ]


def test_heartbeat_error_rejects_only_heartbeat_control_owner(tmp_path: Path) -> None:
    """Heartbeat rejection cannot consume report, status, message, or its waiter."""
    socket = _FakeWebSocket(
        incoming=[
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.register"}}
            ),
            json.dumps(
                {
                    "type": "error",
                    "payload": {
                        "code": "heartbeat_rejected",
                        "message": "heartbeat owner mismatch",
                    },
                }
            ),
            json.dumps(
                {"type": "ack", "payload": {"message_type": "node.report"}}
            ),
            json.dumps(
                {
                    "type": "channel.status.result",
                    "payload": {"request_id": "status-1", "outcome": "accepted"},
                }
            ),
            json.dumps(
                {
                    "type": "ack",
                    "payload": {
                        "message_type": "agent.message",
                        "conversation_id": "conv-1",
                    },
                }
            ),
        ]
    )
    relay = WebRelayAdapter()
    relay.start(lambda _message: None)
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local", heartbeat_interval_seconds=0),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register ack
        heartbeat = asyncio.create_task(manager._send_heartbeat_and_wait_ack())  # noqa: SLF001
        await asyncio.sleep(0)
        await manager.send_json("node.report", {"status": "healthy"})
        await manager.send_json(
            "channel.status",
            _status("status-1", incarnation="inc-a", sequence=1),
        )
        waiter = asyncio.create_task(
            manager.send_json_await_ack("agent.message", {"text": "hello"})
        )
        await asyncio.sleep(0)

        assert [json.loads(frame)["type"] for frame in socket.sent] == [
            "node.register",
            "node.heartbeat",
        ]
        await manager._listen_once()  # noqa: SLF001 - heartbeat error only
        with pytest.raises(RuntimeError, match="heartbeat_rejected"):
            await asyncio.wait_for(heartbeat, timeout=0.1)
        assert not waiter.done()
        for _ in range(3):
            await manager._listen_once()  # noqa: SLF001 - drain untouched business
        assert await waiter == {
            "message_type": "agent.message",
            "conversation_id": "conv-1",
        }

    asyncio.run(exercise())

    assert [json.loads(frame)["type"] for frame in socket.sent] == [
        "node.register",
        "node.heartbeat",
        "node.report",
        "channel.status",
        "agent.message",
    ]
    error_events = [
        event for event in manager.event_log() if event["event"] == "error_ack"
    ]
    assert error_events[-1]["rejected_type"] == "node.heartbeat"
