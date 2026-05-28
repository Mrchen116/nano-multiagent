import asyncio
import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.types import Message, TurnResult
from agent.platform.http_api.app import create_app


class _BlockingRuntime:
    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def run(self, session_id, parts, *, stream=True, run_id=None, controller=None, origin=None, workspace_root=None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id, controller, origin
        try:
            await asyncio.wait_for(self.release.wait(), timeout=1.0)
        except TimeoutError:
            pass
        return TurnResult(
            session_id="sess_interrupt_contract",
            turn_id="turn_interrupt_contract",
            messages=(Message(message_id="msg_interrupt_contract", role="assistant", content="ok"),),
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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-interrupt-running-get"))
        assert response.status_code == 200
        if response.json()["status"] == "running":
            return
        time.sleep(0.01)
    raise AssertionError("run did not enter running status")


def test_interrupt_active_run_returns_interrupted_true_and_run_id(tmp_path: Path) -> None:
    runtime = _BlockingRuntime()
    # No product profile here → stateless fallback store; supply an explicit
    # data_dir-backed test store so HTTP ops without workspace_root resolve.
    client = TestClient(
        create_app(runtime=runtime, session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-interrupt-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-interrupt-submit"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    response = client.post(
        f"/v1/sessions/{session_id}/interrupt",
        headers=_auth_headers("req-interrupt-active"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["interrupted"] is True
    assert payload["run_id"] == run_id

    runtime.release.set()


def test_interrupt_idle_session_returns_interrupted_false(tmp_path: Path) -> None:
    client = TestClient(
        create_app(runtime=_BlockingRuntime(), session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-interrupt-idle-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/interrupt",
        headers=_auth_headers("req-interrupt-idle"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["interrupted"] is False
    assert payload["run_id"] is None


def test_interrupt_unknown_session_returns_404() -> None:
    client = TestClient(create_app(runtime=_BlockingRuntime()))

    response = client.post(
        "/v1/sessions/sess_missing/interrupt",
        headers=_auth_headers("req-interrupt-missing"),
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "session_not_found"
    assert payload["error"]["trace_id"] == "req-interrupt-missing"
