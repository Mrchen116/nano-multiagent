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


def test_session_log_resolution_coalesces_and_expires_at_the_scan_cap(
    tmp_path: Path, monkeypatch
) -> None:
    """Backpressure expires excess lookups without delaying ordinary downstream frames."""
    monkeypatch.setattr(im_connection_module, "_MAX_CONCURRENT_SESSION_LOG_SCANS", 2)
    monkeypatch.setattr(
        im_connection_module, "_SESSION_LOG_RESOLUTION_TIMEOUT_SECONDS", 0.02,
        raising=False,
    )
    scans_started = threading.Event()
    release_scans = threading.Event()
    scan_calls: list[str] = []
    heartbeat_triggers: list[tuple[str, str]] = []

    def blocked_resolve(*, workspace_root: Path, conversation_id: str, agent_id: str):
        del workspace_root, agent_id
        scan_calls.append(conversation_id)
        if len(scan_calls) == 2:
            scans_started.set()
        assert release_scans.wait(timeout=1)
        return None

    monkeypatch.setattr(
        im_connection_module, "_resolve_session_jsonl_path", blocked_resolve
    )
    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {"type": "session.log.resolve", "payload": {
                    "request_id": "same-1", "agent_id": "agent-a", "conversation_id": "same",
                }}
            ),
            json.dumps(
                {"type": "session.log.resolve", "payload": {
                    "request_id": "same-2", "agent_id": "agent-a", "conversation_id": "same",
                }}
            ),
            json.dumps(
                {"type": "session.log.resolve", "payload": {
                    "request_id": "other", "agent_id": "agent-a", "conversation_id": "other",
                }}
            ),
            json.dumps(
                {"type": "session.log.resolve", "payload": {
                    "request_id": "overflow", "agent_id": "agent-a", "conversation_id": "overflow",
                }}
            ),
            json.dumps(
                {"type": "heartbeat.trigger", "payload": {
                    "agent_id": "agent-a", "reason": "manual",
                }}
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
        heartbeat_trigger=lambda agent_id, reason: heartbeat_triggers.append((agent_id, reason)),
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )

    async def exercise() -> None:
        await manager.connect_once()
        for _ in range(6):
            await manager._listen_once()  # noqa: SLF001 - downstream contract exercise
        assert await asyncio.to_thread(scans_started.wait, 0.5)
        await asyncio.sleep(0.05)
        overflow = [
            json.loads(frame)["payload"]
            for frame in socket.sent
            if "session.log.resolved" in frame
            and json.loads(frame)["payload"]["request_id"] == "overflow"
        ]
        assert overflow == [
            {
                "request_id": "overflow",
                "node_id": "n1",
                "agent_id": "agent-a",
                "conversation_id": "overflow",
                "source_jsonl_path": None,
            }
        ]
        assert not manager._session_log_tasks  # noqa: SLF001 - expiry must retire waiters
        release_scans.set()
        await manager.close()

    asyncio.run(exercise())

    assert scan_calls == ["same", "other"]
    assert heartbeat_triggers == [("agent-a", "manual")]
