"""E2E tests for human chat chain including SSE reconnect."""

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


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for raw_block in body.strip().split("\n\n"):
        block = raw_block.strip()
        if not block or block.startswith(":"):
            continue
        parsed: dict[str, object] = {}
        for line in block.splitlines():
            if line.startswith("id: "):
                parsed["id"] = int(line[4:])
            elif line.startswith("event: "):
                parsed["event"] = line[7:]
            elif line.startswith("data: "):
                parsed["data"] = json.loads(line[6:])
        if parsed:
            events.append(parsed)
    return events


def test_human_chat_chain_and_sse_reconnect(tmp_path: Path) -> None:
    """Validate full chat chain and incremental SSE replay after reconnect."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        bob_id = _create_user(client, "bob")

        conversation_resp = client.post(
            "/im/v1/conversations",
            json={"title": "chat", "participant_ids": [alice_id, bob_id]},
        )
        assert conversation_resp.status_code == 201
        conversation_id = conversation_resp.json()["id"]

        first_msg = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "first"},
        )
        second_msg = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": bob_id, "content": "second"},
        )
        assert first_msg.status_code == 201
        assert second_msg.status_code == 201

        initial_stream = client.get(
            f"/im/v1/conversations/{conversation_id}/events?max_events=20&timeout_seconds=0.05"
        )
        assert initial_stream.status_code == 200
        initial_events = _parse_sse_events(initial_stream.text)
        assert len(initial_events) == 4

        last_event_id = int(initial_events[-1]["id"])

        third_msg = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "third"},
        )
        assert third_msg.status_code == 201
        third_message_id = third_msg.json()["id"]

        incremental_stream = client.get(
            f"/im/v1/conversations/{conversation_id}/events?after_event_id={last_event_id}&timeout_seconds=0.05"
        )
        assert incremental_stream.status_code == 200
        incremental_events = _parse_sse_events(incremental_stream.text)

        assert len(incremental_events) == 2
        assert {event["data"]["message_id"] for event in incremental_events} == {third_message_id}
        assert {event["event"] for event in incremental_events} == {"message.sent", "message.delivered"}
