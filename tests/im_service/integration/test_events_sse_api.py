"""Integration tests for IM conversation SSE event streaming."""

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


def _parse_sse_payload(body: str) -> list[dict[str, object]]:
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


def test_events_sse_supports_last_event_id_reconnect(tmp_path: Path) -> None:
    """Read initial events then reconnect and receive only incremental events."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)

        first = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "first"},
        )
        assert first.status_code == 201
        first_message_id = first.json()["id"]

        first_stream = client.get(
            f"/im/v1/conversations/{conversation_id}/events?max_events=10&timeout_seconds=0.05"
        )
        assert first_stream.status_code == 200
        first_events = _parse_sse_payload(first_stream.text)
        assert len(first_events) == 2
        assert {event["event"] for event in first_events} == {"message.sent", "message.delivered"}
        assert {event["data"]["message_id"] for event in first_events} == {first_message_id}

        last_event_id = int(first_events[-1]["id"])

        second = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "second"},
        )
        assert second.status_code == 201
        second_message_id = second.json()["id"]

        second_stream = client.get(
            f"/im/v1/conversations/{conversation_id}/events?timeout_seconds=0.05",
            headers={"Last-Event-ID": str(last_event_id)},
        )
        assert second_stream.status_code == 200
        incremental_events = _parse_sse_payload(second_stream.text)

        assert len(incremental_events) == 2
        assert {event["data"]["message_id"] for event in incremental_events} == {second_message_id}
        assert all(int(event["id"]) > last_event_id for event in incremental_events)
