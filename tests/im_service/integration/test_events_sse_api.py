"""集成测试：用户维 WebSocket 实时事件。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app


def _create_user(client: TestClient, username: str) -> str:
    response = client.post(
        "/im/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_conversation(client: TestClient, participant_id: str) -> str:
    response = client.post(
        "/im/v1/conversations",
        json={"title": "chat", "participant_ids": [participant_id]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_user_stream_resume_replays_persisted_events(tmp_path: Path) -> None:
    """resume after_event_id=0 回放已有 message 事件。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "first"},
        )
        assert first.status_code == 201

        with client.websocket_connect(f"/im/ws/user?user_id={alice_id}") as websocket:
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
