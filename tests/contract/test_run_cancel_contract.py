import time
from threading import Event

from fastapi.testclient import TestClient

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.platform.http_api.app import create_app


class _BlockingRuntime:
    def __init__(self) -> None:
        self.release = Event()

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del session_id
        del parts
        del stream
        self.release.wait(timeout=1.0)
        return TurnResult(
            session_id="sess_cancel_contract",
            turn_id="turn_cancel_contract",
            messages=(Message(message_id="msg_cancel_contract", role="assistant", content="ok"),),
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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-cancel-running-get"))
        assert response.status_code == 200
        if response.json()["status"] == "running":
            return
        time.sleep(0.01)
    raise AssertionError("run did not enter running status")


def test_run_cancel_contract_for_running_and_terminal_states() -> None:
    runtime = _BlockingRuntime()
    client = TestClient(create_app(runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-cancel-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-cancel-submit"),
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    cancelled = client.post(
        f"/v1/runs/{run_id}/cancel",
        headers=_auth_headers("req-cancel-running"),
    )
    assert cancelled.status_code == 200
    payload = cancelled.json()
    assert payload["run_id"] == run_id
    assert payload["status"] == "cancelled"

    idempotent = client.post(
        f"/v1/runs/{run_id}/cancel",
        headers=_auth_headers("req-cancel-idempotent"),
    )
    assert idempotent.status_code == 200
    assert idempotent.json()["status"] == "cancelled"

    runtime.release.set()


def test_cancel_unknown_run_uses_unified_error_shape() -> None:
    client = TestClient(create_app(runtime=_BlockingRuntime()))

    response = client.post(
        "/v1/runs/run_missing/cancel",
        headers=_auth_headers("req-cancel-missing"),
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "run_not_found"
    assert payload["error"]["trace_id"] == "req-cancel-missing"
