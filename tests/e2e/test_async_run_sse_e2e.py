from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app


class _RuntimeStub:
    def run(self, session_id: str, parts, *, stream: bool = True):  # noqa: ANN001, ANN201
        del parts
        del stream
        return TurnResult(
            session_id=session_id,
            turn_id="turn_sse_e2e",
            messages=(Message(message_id="msg_sse_e2e", role="assistant", content="pong-sse"),),
            completed=True,
            stop_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_async_submission_emits_sse_events_e2e() -> None:
    client = TestClient(create_app(runtime=_RuntimeStub()))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-e2e-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-sse-e2e-submit"),
    )
    assert submitted.status_code == 202

    response = client.get(
        "/v1/events?max_events=10&timeout_seconds=0.2",
        headers=_auth_headers("req-sse-e2e-events"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_status" in response.text
    assert "event: text_delta" in response.text
    assert "event: turn_end" in response.text
