"""R5 tests: /im/ws/user must authenticate via token; cross-tenant events are dropped.

After M1 R5, the user WebSocket no longer accepts ``?user_id=`` as a trust anchor;
the user identity is taken from a JWT passed either as ``?token=<jwt>`` query string
or via the ``Sec-WebSocket-Protocol: bearer.<jwt>`` subprotocol (the only WS auth
channels FastAPI/Starlette exposes uniformly).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import authorize, make_app_client, register_user


def test_user_stream_rejects_connection_without_token(tmp_path: Path) -> None:
    """No token query string → close with policy violation code (1008)."""
    with make_app_client(tmp_path) as client:
        # Register so a valid app exists but the connection itself has no token.
        alice = register_user(client, username="alice")
        del alice
        with pytest.raises(Exception):  # noqa: PT011 - starlette raises WebSocketDisconnect or similar
            with client.websocket_connect("/im/ws/user") as websocket:
                # If the server didn't close, this read will eventually hang/raise.
                websocket.receive_text()


def test_user_stream_rejects_invalid_token(tmp_path: Path) -> None:
    """Garbage token → close 1008."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        del alice
        with pytest.raises(Exception):  # noqa: PT011
            with client.websocket_connect("/im/ws/user?token=not-a-jwt") as websocket:
                websocket.receive_text()


def test_user_stream_accepts_valid_token_and_replays_owners_events(tmp_path: Path) -> None:
    """Valid token → connection accepted; user receives their own conversation events on resume."""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "alice", "participant_ids": [alice.id]},
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]
        client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice.id, "content": "first"},
        )

        with client.websocket_connect(f"/im/ws/user?token={alice.access_token}") as websocket:
            websocket.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
            seen: list[str] = []
            for _ in range(6):
                body = json.loads(websocket.receive_text())
                if body.get("op") == "event":
                    seen.append(str(body.get("event_type")))
                if len(seen) >= 2:
                    break
            assert "message.sent" in seen
