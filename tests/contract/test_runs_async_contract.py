import time

from fastapi.testclient import TestClient

from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.platform.http_api.app import create_app


class _RuntimeStub:
    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del parts
        del stream
        return TurnResult(
            session_id=session_id,
            turn_id="turn_contract_async",
            messages=(Message(message_id="msg_contract_async", role="assistant", content="async-ok"),),
            completed=True,
            stop_reason="completed",
        )


class _RetryThenSuccessRuntime:
    def __init__(self, *, fail_times: int) -> None:
        self._fail_times = fail_times
        self._calls = 0

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del parts
        del stream
        del run_id
        self._calls += 1
        if self._calls <= self._fail_times:
            raise ModelError(f"upstream flaky #{self._calls}", retryable=True)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_contract_retry",
            messages=(Message(message_id="msg_contract_retry", role="assistant", content="retry-ok"),),
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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-runs-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_messages_async_contract_submit_and_get_run() -> None:
    client = TestClient(create_app(runtime=_RuntimeStub()))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-runs-submit"),
    )
    assert submitted.status_code == 202
    assert submitted.headers["x-request-id"] == "req-runs-submit"

    payload = submitted.json()
    assert set(payload.keys()) == {"run_id", "session_id", "status"}
    assert payload["session_id"] == session_id
    assert payload["status"] in {"queued", "running"}

    terminal = _wait_for_terminal_run(client, payload["run_id"])
    assert set(terminal.keys()) == {
        "run_id",
        "session_id",
        "status",
        "created_at",
        "updated_at",
        "turn_id",
        "stop_reason",
        "error",
        "usage",
    }
    assert terminal["status"] == "completed"
    assert terminal["turn_id"] == "turn_contract_async"
    assert terminal["stop_reason"] == "completed"
    assert terminal["error"] is None
    assert terminal["usage"] is None


def test_get_run_not_found_uses_unified_error_shape() -> None:
    client = TestClient(create_app(runtime=_RuntimeStub()))

    response = client.get(
        "/v1/runs/run_missing",
        headers=_auth_headers("req-runs-missing"),
    )

    assert response.status_code == 404
    payload = response.json()
    assert set(payload.keys()) == {"error"}
    assert set(payload["error"].keys()) == {"code", "message", "retryable", "trace_id"}
    assert payload["error"]["code"] == "run_not_found"
    assert payload["error"]["trace_id"] == "req-runs-missing"
    assert response.headers["x-request-id"] == "req-runs-missing"


def test_session_sse_run_status_contract_includes_retry_progress_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        "nano_multiagent.runs.registry._wait_with_cancel",
        lambda _event, _seconds: False,
    )
    client = TestClient(create_app(runtime=_RetryThenSuccessRuntime(fail_times=2)))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-retry-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-runs-retry-submit"),
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]

    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"

    response = client.get(
        f"/v1/sessions/{session_id}/events?max_events=30&timeout_seconds=0.1",
        headers=_auth_headers("req-runs-retry-events"),
    )
    assert response.status_code == 200
    body = response.text
    assert "event: run_status" in body
    assert '"attempt":1' in body
    assert '"next_delay":0.5' in body
    assert '"cooldown":0.0' in body
    assert '"last_error":{"code":"model_error","message":"upstream flaky #1","retryable":true}' in body
