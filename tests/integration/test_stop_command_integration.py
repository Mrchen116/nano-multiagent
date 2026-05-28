"""Integration test: session interrupt API with blocking runtime."""

import asyncio
import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.core.types import Message, TurnResult


class _BlockingRuntime:
    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def run(self, session_id, parts, *, stream=True, run_id=None, controller=None, origin=None):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id, controller, origin
        try:
            await asyncio.wait_for(self.release.wait(), timeout=1.0)
        except TimeoutError:
            pass
        return TurnResult(
            session_id="sess_stop_integration",
            turn_id="turn_stop_integration",
            messages=(Message(message_id="msg_stop_integration", role="assistant", content="ok"),),
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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-stop-integration-get"))
        assert response.status_code == 200
        if response.json()["status"] == "running":
            return
        time.sleep(0.01)
    raise AssertionError("run did not enter running status")


def test_interrupted_run_returns_interrupted_true_and_run_id(tmp_path: Path) -> None:
    runtime = _BlockingRuntime()
    # No product profile → stateless fallback store; supply an explicit
    # data_dir-backed test store so HTTP ops without workspace_root resolve.
    client = TestClient(
        create_app(runtime=runtime, session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-stop-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "stop me"}]},
        headers=_auth_headers("req-stop-integration-submit"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    interrupted = client.post(
        f"/v1/sessions/{session_id}/interrupt",
        headers=_auth_headers("req-stop-integration-interrupt"),
    )
    assert interrupted.status_code == 200
    payload = interrupted.json()
    assert payload["interrupted"] is True
    assert payload["run_id"] == run_id

    runtime.release.set()


def test_interrupt_idle_session_returns_not_interrupted(tmp_path: Path) -> None:
    client = TestClient(create_app(session_store=JsonlSessionStore(data_dir=tmp_path)))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-stop-idle-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/interrupt",
        headers=_auth_headers("req-stop-idle-interrupt"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["interrupted"] is False
    assert payload["run_id"] is None
