"""用户流与 /im/v1/sync 的契约测试（替代按会话 SSE）。"""

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


def test_sync_contract_returns_snapshot_and_max_event_id(tmp_path: Path) -> None:
    """GET /im/v1/sync 返回会话列表与全局 max_event_id。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello"},
        )
        assert created.status_code == 201

        synced = client.get("/im/v1/sync")
        assert synced.status_code == 200
        payload = synced.json()
        assert "items" in payload
        assert "max_event_id" in payload
        assert payload["max_event_id"] > 0
        assert any(item["id"] == conversation_id for item in payload["items"])


def test_user_stream_contract_emits_json_events(tmp_path: Path) -> None:
    """WebSocket /im/ws/user 在 resume 时回放已持久化消息的 event 帧。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        posted = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello"},
        )
        assert posted.status_code == 201
        with client.websocket_connect(f"/im/ws/user?user_id={alice_id}") as websocket:
            websocket.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
            seen: list[dict[str, object]] = []
            for _ in range(4):
                raw = websocket.receive_text()
                body = json.loads(raw)
                seen.append(body)
                if body.get("op") == "event" and body.get("event_type") == "message.delivered":
                    break
            event_types = [b.get("event_type") for b in seen if b.get("op") == "event"]
            assert "message.sent" in event_types
            assert "message.delivered" in event_types
