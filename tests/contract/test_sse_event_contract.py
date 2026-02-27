from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app


class _RuntimeStub:
    def run(self, session_id: str, parts, *, stream: bool = True):  # noqa: ANN001, ANN201
        del parts
        del stream
        return TurnResult(
            session_id=session_id,
            turn_id="turn_sse_contract",
            messages=(Message(message_id="msg_sse_contract", role="assistant", content="contract-sse"),),
            completed=True,
            stop_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_global_sse_contract_returns_event_stream_frames() -> None:
    client = TestClient(create_app(runtime=_RuntimeStub()))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-contract-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-sse-contract-submit"),
    )
    assert submitted.status_code == 202

    response = client.get(
        "/v1/events?max_events=8&timeout_seconds=0.1",
        headers=_auth_headers("req-sse-contract-global"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: run_status" in body
    assert "event: text_delta" in body
    assert "event: turn_end" in body


def test_session_sse_contract_filters_by_session_id() -> None:
    client = TestClient(create_app(runtime=_RuntimeStub()))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-contract-create-2"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "session-only"}]},
        headers=_auth_headers("req-sse-contract-submit-2"),
    )
    assert submitted.status_code == 202

    response = client.get(
        f"/v1/sessions/{session_id}/events?max_events=8&timeout_seconds=0.1",
        headers=_auth_headers("req-sse-contract-session"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_status" in response.text
    assert session_id in response.text
