"""Concurrency contract for Gateway-side transcript discovery."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import personal_assistant.ws.im_connection as im_connection_module
from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


def test_session_log_scan_does_not_block_gateway_receive_owner(
    tmp_path: Path, monkeypatch
) -> None:
    """A second resolve frame is received while the first local scan is still blocked."""
    scan_started = threading.Event()
    release_scan = threading.Event()
    scan_calls: list[str] = []

    def slow_resolve(*, workspace_root: Path, conversation_id: str, agent_id: str):
        del workspace_root, agent_id
        scan_calls.append(conversation_id)
        scan_started.set()
        assert release_scan.wait(timeout=1)
        return f"/gateway/{conversation_id}.jsonl"

    monkeypatch.setattr(
        im_connection_module, "_resolve_session_jsonl_path", slow_resolve
    )
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "session.log.resolve",
                    "payload": {
                        "request_id": "session-log-1",
                        "agent_id": "agent-a",
                        "conversation_id": "conversation-1",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "session.log.resolve",
                    "payload": {
                        "request_id": "session-log-2",
                        "agent_id": "agent-a",
                        "conversation_id": "conversation-2",
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
        agent_config_provider=lambda _agent_id: {"workspace_root": "/gateway/workspace"},
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        await manager._listen_once()  # noqa: SLF001 - register acknowledgement
        await asyncio.wait_for(manager._listen_once(), timeout=0.1)  # noqa: SLF001
        assert await asyncio.to_thread(scan_started.wait, 0.5)
        await asyncio.wait_for(manager._listen_once(), timeout=0.1)  # noqa: SLF001
        release_scan.set()
        for _ in range(20):
            if len([frame for frame in socket.sent if "session.log.resolved" in frame]) == 1:
                break
            await asyncio.sleep(0.01)
        socket.incoming.append(
            json.dumps(
                {
                    "type": "ack",
                    "payload": {"message_type": "session.log.resolved"},
                }
            )
        )
        await manager._listen_once()  # noqa: SLF001 - first resolve acknowledgement
        for _ in range(20):
            if len([frame for frame in socket.sent if "session.log.resolved" in frame]) == 2:
                break
            await asyncio.sleep(0.01)
        await manager.close()

    asyncio.run(exercise())

    assert scan_calls == ["conversation-1", "conversation-2"]
    resolved = [
        json.loads(frame)["payload"]
        for frame in socket.sent
        if "session.log.resolved" in frame
    ]
    assert {item["conversation_id"] for item in resolved} == {
        "conversation-1",
        "conversation-2",
    }
