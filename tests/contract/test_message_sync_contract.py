import time

from fastapi.testclient import TestClient

from agent.core.types import Message, TurnResult
from agent.platform.http_api.app import create_app


class StubRuntime:
    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, origin=None) -> TurnResult:  # noqa: ANN001
        del parts
        del stream
        del origin
        return TurnResult(
            session_id=session_id,
            turn_id="turn_contract",
            messages=(Message(message_id="msg_contract", role="assistant", content="contract-ok"),),
            completed=True,
            stop_reason="completed",
        )


class MissingSessionRuntime:
    async def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, origin=None) -> TurnResult:  # noqa: ANN001
        del parts
        del stream
        del origin
        raise ValueError(f"session does not exist: {session_id}")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-runs-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_submit_message_contract_returns_run_handle() -> None:
    # POST /v1/sessions/{id}/messages returns an async run handle (not a sync TurnResult).
    client = TestClient(create_app(runtime=StubRuntime()))
    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-message-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-message-sync"),
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-message-sync"
    payload = response.json()
    assert set(payload.keys()) == {"run_id", "anchor_sequence", "injected", "status"}
    assert isinstance(payload["run_id"], str)
    assert payload["status"] in {"queued", "running"}

    terminal = _wait_for_terminal_run(client, payload["run_id"])
    assert terminal["status"] == "completed"
    assert terminal["output_text"] == "contract-ok"


def test_submit_message_not_found_uses_unified_error_with_trace_id() -> None:
    client = TestClient(create_app(runtime=MissingSessionRuntime()))

    response = client.post(
        "/v1/sessions/sess_missing/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-message-missing"),
    )

    assert response.status_code == 404
    payload = response.json()
    assert set(payload.keys()) == {"error"}
    assert set(payload["error"].keys()) == {"code", "message", "retryable", "trace_id"}
    assert payload["error"]["code"] == "session_not_found"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["trace_id"] == "req-message-missing"
    assert response.headers["x-request-id"] == "req-message-missing"
