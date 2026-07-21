"""用户流与 /im/v1/sync 的契约测试（替代按会话 SSE）。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from tests.im_service._auth_helpers import authorize, register_user


def _create_conversation(client: TestClient, participant_id: str) -> str:
    response = client.post(
        "/im/v1/conversations",
        json={"title": "chat", "participant_ids": [participant_id]},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_sync_contract_returns_snapshot_and_max_event_id(tmp_path: Path) -> None:
    """GET /im/v1/sync 返回会话列表与全局 max_event_id。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        conversation_id = _create_conversation(client, alice.id)
        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice.id, "content": "hello"},
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
        alice = register_user(client, username="alice")
        authorize(client, alice)
        conversation_id = _create_conversation(client, alice.id)
        posted = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice.id, "content": "hello"},
        )
        assert posted.status_code == 201
        with client.websocket_connect(
            f"/im/ws/user?token={alice.access_token}"
        ) as websocket:
            websocket.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
            seen: list[dict[str, object]] = []
            for _ in range(4):
                raw = websocket.receive_text()
                body = json.loads(raw)
                seen.append(body)
                if (
                    body.get("op") == "event"
                    and body.get("event_type") == "message.delivered"
                ):
                    break
            event_types = [b.get("event_type") for b in seen if b.get("op") == "event"]
            assert "message.sent" in event_types
            assert "message.delivered" in event_types


def test_user_stream_replays_boundary_without_runtime_provenance(
    tmp_path: Path,
) -> None:
    """A resumed owner receives one safe timeline boundary under its durable event id."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        from tests.im_service._auth_helpers import seed_user_under_owner

        agent_user_id = seed_user_under_owner(
            client,
            username="agent:planner",
            owner_id=alice.owner_id,
        )
        conversation = client.post(
            "/im/v1/conversations",
            json={
                "title": "Planner",
                "participant_ids": [alice.id, agent_user_id],
            },
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["id"]
        anchor = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice.id, "content": "use new runtime"},
        )
        assert anchor.status_code == 201, anchor.text

        with client.websocket_connect("/im/ws/gateway") as gateway:
            gateway.send_json(
                {
                    "type": "node.register",
                    "payload": {"node_id": "node-1", "agents": ["planner"]},
                }
            )
            assert gateway.receive_json()["type"] == "ack"
            gateway.send_json(
                {
                    "type": "agent.config.boundary",
                    "payload": {
                        "boundary_id": "boundary-stream-1",
                        "node_id": "node-1",
                        "conversation_id": conversation_id,
                        "agent_id": "planner",
                        "before_message_id": anchor.json()["id"],
                        "runtime_fingerprint": "secret-runtime-fingerprint",
                        "fingerprint_schema": "v1",
                        "profile_version": 9,
                        "applied_at": "2026-07-21T00:00:00Z",
                    },
                }
            )
            acknowledged = gateway.receive_json()
            assert acknowledged["type"] == "ack"

        boundary_event_id = acknowledged["payload"]["event_id"]
        with client.websocket_connect(
            f"/im/ws/user?token={alice.access_token}"
        ) as user_stream:
            user_stream.send_text(
                json.dumps({"op": "resume", "after_event_id": boundary_event_id - 1})
            )
            replayed = json.loads(user_stream.receive_text())

        assert replayed["op"] == "event"
        assert replayed["event_type"] == "agent.config.changed"
        assert replayed["event_id"] == boundary_event_id
        assert replayed["conversation_id"] == conversation_id
        assert replayed["data"] == {
            "id": "boundary-stream-1",
            "conversation_id": conversation_id,
            "agent_id": "planner",
            "before_message_id": anchor.json()["id"],
            "applied_at": "2026-07-21T00:00:00Z",
            "event_id": boundary_event_id,
            "message_id": None,
            "delivery_status": "completed",
            "created_at": replayed["data"]["created_at"],
        }
        assert "secret-runtime-fingerprint" not in json.dumps(replayed)
        assert "profile_version" not in replayed["data"]
