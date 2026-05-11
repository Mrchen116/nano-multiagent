"""E2E：人类聊天链路与用户 WebSocket 增量事件。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from IM.app import create_app

from tests.im_service._auth_helpers import authorize, register_user, seed_user_under_owner


def test_human_chat_chain_and_user_stream_incremental(tmp_path: Path) -> None:
    """完整发消息链，经单用户 WebSocket 回放历史并接收增量。"""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        alice_id = alice.id
        bob_id = seed_user_under_owner(client, username="bob", owner_id=alice.owner_id)

        first_conversation = client.post(
            "/im/v1/conversations",
            json={"title": "chat-alice", "participant_ids": [alice_id]},
        )
        second_conversation = client.post(
            "/im/v1/conversations",
            json={"title": "chat-bob", "participant_ids": [bob_id]},
        )
        assert first_conversation.status_code == 201
        assert second_conversation.status_code == 201
        conversation_id = first_conversation.json()["id"]

        first_msg = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "first"},
        )
        second_msg = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={
                "sender_user_id": alice_id,
                "sender_type": "agent",
                "content": "second",
                "attachments": [{"url": "file:///tmp/second.txt", "file_name": "second.txt"}],
            },
        )
        assert first_msg.status_code == 201
        assert second_msg.status_code == 201

        with client.websocket_connect(f"/im/ws/user?user_id={alice_id}") as websocket:
            websocket.send_text(json.dumps({"op": "resume", "after_event_id": 0}))
            initial_events: list[dict[str, object]] = []
            while len(initial_events) < 4:
                body = json.loads(websocket.receive_text())
                if body.get("op") == "event":
                    initial_events.append(body)
            assert len(initial_events) == 4

            third_msg = client.post(
                f"/im/v1/conversations/{conversation_id}/messages",
                json={"sender_user_id": alice_id, "sender_type": "system", "content": "third"},
            )
            assert third_msg.status_code == 201
            third_message_id = third_msg.json()["id"]

            incremental_events: list[dict[str, object]] = []
            while len(incremental_events) < 2:
                body = json.loads(websocket.receive_text())
                if body.get("op") == "event":
                    incremental_events.append(body)
            assert {str((b.get("data") or {}).get("message_id")) for b in incremental_events} == {third_message_id}
            assert {b.get("event_type") for b in incremental_events} == {"message.sent", "message.delivered"}
            assert (incremental_events[0].get("data") or {}).get("sender_type") == "system"
