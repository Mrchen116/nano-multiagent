"""Contract tests for conversation events SSE endpoint."""

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


def test_events_endpoint_contract_returns_event_stream(tmp_path: Path) -> None:
    """Return text/event-stream payload with persisted message events."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)
        created = client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello"},
        )
        assert created.status_code == 201

        streamed = client.get(
            f"/im/v1/conversations/{conversation_id}/events?max_events=10&timeout_seconds=0.05"
        )

        assert streamed.status_code == 200
        assert streamed.headers["content-type"].startswith("text/event-stream")
        assert "event: message.sent" in streamed.text
        assert "event: message.delivered" in streamed.text
        assert '"delivery_status":"completed"' in streamed.text


def test_events_endpoint_contract_rejects_invalid_cursor(tmp_path: Path) -> None:
    """Reject non-integer cursor values with a stable 400 response."""
    app = create_app(db_path=tmp_path / "im.db")
    with TestClient(app) as client:
        alice_id = _create_user(client, "alice")
        conversation_id = _create_conversation(client, alice_id)

        response = client.get(
            f"/im/v1/conversations/{conversation_id}/events?after_event_id=not-int"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "after_event_id must be an integer"
