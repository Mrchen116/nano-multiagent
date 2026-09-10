"""Distinguish broker failures from permission requests that actually ended."""

import json

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager
from ._im_connection_helpers import _FakeWebSocket, _connect_fake, _minimal_reporter


@pytest.mark.asyncio
async def test_permission_handler_failure_is_logged_and_does_not_claim_request_ended(
    tmp_path, caplog
):
    def fail(payload):
        raise RuntimeError("broker unavailable")

    socket = _FakeWebSocket(
        incoming=[
            json.dumps({"type": "ack", "payload": {"message_type": "node.register"}}),
            json.dumps(
                {
                    "type": "agent.work.permission",
                    "payload": {"request_id": "p", "decision": "deny"},
                }
            ),
        ]
    )
    manager = IMConnectionManager(
        config=IMConnectionConfig(url="http://im.local", token="token"),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=WebRelayAdapter(),
        work_permission_handler=fail,
        connect=lambda url, headers: _connect_fake(socket, [], url, headers),
    )
    try:
        await manager.connect_once()
        await manager._listen_once()
        await manager._listen_once()
        result = next(
            json.loads(frame)["payload"]
            for frame in socket.sent
            if json.loads(frame)["type"] == "agent.work.permission.result"
        )
        assert result["ok"] is False
        assert result["error"] == "permission_decision_failed"
        assert "broker unavailable" in caplog.text
    finally:
        await manager.close()
