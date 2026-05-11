"""集成测试：用户维 WebSocket 实时事件。"""

import json
from pathlib import Path

from .conftest import authorize, make_app_client, register_user


def test_user_stream_resume_replays_persisted_events(tmp_path: Path) -> None:
    """resume after_event_id=0 回放已有 message 事件。"""
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        conversation = client.post(
            "/im/v1/conversations",
            json={"title": "chat", "participant_ids": [alice.id]},
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]
        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice.id, "content": "first"},
        )
        assert first.status_code == 201

        with client.websocket_connect(f"/im/ws/user?token={alice.access_token}") as websocket:
            websocket.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
            event_types: list[str] = []
            for _ in range(6):
                body = json.loads(websocket.receive_text())
                if body.get("op") == "event":
                    event_types.append(str(body.get("event_type")))
                if len(event_types) >= 2:
                    break
            assert "message.sent" in event_types
            assert "message.delivered" in event_types
