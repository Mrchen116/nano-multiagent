import time
from threading import Event

from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.platform.http_api.app import create_app


class _RecordingBlockingRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.release = Event()

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        self.calls.append({"session_id": session_id, "parts": parts, "stream": stream})
        self.release.wait(timeout=1.0)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_cancel_e2e",
            messages=(Message(message_id="msg_cancel_e2e", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_running(client: TestClient, run_id: str, *, timeout_seconds: float = 1.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-cancel-e2e-get"))
        assert response.status_code == 200
        if response.json()["status"] == "running":
            return
        time.sleep(0.01)
    raise AssertionError("run did not enter running status")


def test_submit_async_then_cancel_run_e2e() -> None:
    runtime = _RecordingBlockingRuntime()
    client = TestClient(create_app(runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-cancel-e2e-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-cancel-e2e-submit"),
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    cancelled = client.post(
        f"/v1/runs/{run_id}/cancel",
        headers=_auth_headers("req-cancel-e2e-cancel"),
    )
    assert cancelled.status_code == 200
    assert cancelled.headers["x-request-id"] == "req-cancel-e2e-cancel"
    assert cancelled.json()["status"] == "cancelled"

    runtime.release.set()

    assert len(runtime.calls) == 1
    assert runtime.calls[0]["session_id"] == session_id
    assert runtime.calls[0]["parts"] == [{"type": "text", "text": "ping"}]
    assert runtime.calls[0]["stream"] is False
