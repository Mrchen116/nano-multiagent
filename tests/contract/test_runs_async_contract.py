import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.errors import ModelError
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.types import Message, TurnResult
from agent.platform.http_api.app import create_app


class _RuntimeStub:
    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, origin=None, workspace_root=None):  # noqa: ANN001, ANN201
        del parts
        del stream
        del origin
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

    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None):  # noqa: ANN001, ANN201
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


def test_messages_async_contract_submit_and_get_run(tmp_path: Path) -> None:
    client = TestClient(
        create_app(runtime=_RuntimeStub(), session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-runs-submit"),
    )
    assert submitted.status_code == 200
    assert submitted.headers["x-request-id"] == "req-runs-submit"

    payload = submitted.json()
    assert set(payload.keys()) == {"run_id", "anchor_sequence", "injected", "status"}
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
        "output_text",
        "error",
        "usage",
    }
    assert terminal["status"] == "completed"
    assert terminal["turn_id"] == "turn_contract_async"
    assert terminal["stop_reason"] == "completed"
    assert terminal["output_text"] == "async-ok"
    assert terminal["error"] is None
    assert terminal["usage"] is None


def test_get_run_not_found_uses_unified_error_shape(tmp_path: Path) -> None:
    client = TestClient(
        create_app(runtime=_RuntimeStub(), session_store=JsonlSessionStore(data_dir=tmp_path))
    )

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


def test_session_sse_events_include_run_status_on_completion(tmp_path: Path) -> None:
    # Verify that `run_status` SSE events are published to the session event stream
    # after a run completes.  Retry-progress fields (attempt/next_delay/cooldown)
    # are no longer produced at the RunsRegistry layer; transient retry is handled
    # inside AgentLoop, so those fields are omitted here.
    client = TestClient(
        create_app(runtime=_RuntimeStub(), session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-sse-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-runs-sse-submit"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    _wait_for_terminal_run(client, run_id)

    response = client.get(
        f"/v1/events?after_sequence=0&max_events=30&timeout_seconds=0.1",
        headers=_auth_headers("req-runs-sse-events"),
    )
    assert response.status_code == 200
    body = response.text
    assert "event: run_status" in body
    assert '"status":"completed"' in body
