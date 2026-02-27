import time

from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.app import create_app


class _RecordingRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, session_id: str, parts, *, stream: bool = True):  # noqa: ANN001, ANN201
        self.calls.append(
            {
                "session_id": session_id,
                "parts": parts,
                "stream": stream,
            }
        )
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_e2e",
            messages=(Message(message_id="msg_async_e2e", role="assistant", content="pong-async"),),
            completed=True,
            stop_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 1.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-async-e2e-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_create_session_then_submit_async_message_e2e() -> None:
    runtime = _RecordingRuntime()
    client = TestClient(create_app(runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-async-e2e-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-async-e2e-submit"),
    )

    assert submitted.status_code == 202
    assert submitted.headers["x-request-id"] == "req-async-e2e-submit"

    submit_payload = submitted.json()
    assert submit_payload["session_id"] == session_id
    assert submit_payload["run_id"].startswith("run_")

    terminal = _wait_for_terminal_run(client, submit_payload["run_id"])
    assert terminal["status"] == "completed"
    assert terminal["turn_id"] == "turn_async_e2e"

    assert len(runtime.calls) == 1
    assert runtime.calls[0]["session_id"] == session_id
    assert runtime.calls[0]["parts"] == [{"type": "text", "text": "ping"}]
    assert runtime.calls[0]["stream"] is False
