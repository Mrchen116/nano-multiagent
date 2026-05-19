import time
from threading import Event
from pathlib import Path

from fastapi.testclient import TestClient

from agent.platform.http_api.app import create_app
from agent.core.types import Message, TurnResult


class _BlockingRuntime:
    def __init__(self) -> None:
        self.release = Event()

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, origin=None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, origin
        self.release.wait(timeout=1.0)
        return TurnResult(
            session_id="sess_cancel_integration",
            turn_id="turn_cancel_integration",
            messages=(Message(message_id="msg_cancel_integration", role="assistant", content="ok"),),
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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-cancel-integration-get"))
        assert response.status_code == 200
        if response.json()["status"] == "running":
            return
        time.sleep(0.01)
    raise AssertionError("run did not enter running status")


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-cancel-integration-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_cancelled_run_status_is_reflected_in_api(tmp_path: Path) -> None:
    runtime = _BlockingRuntime()
    client = TestClient(create_app(runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-cancel-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "cancel"}]},
        headers=_auth_headers("req-cancel-integration-submit"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    cancelled = client.post(
        f"/v1/runs/{run_id}/cancel",
        headers=_auth_headers("req-cancel-integration-cancel"),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    runtime.release.set()

    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "cancelled"
