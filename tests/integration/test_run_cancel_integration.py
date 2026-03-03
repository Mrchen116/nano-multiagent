import time
from threading import Event
from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.session.entries import SessionEntryKind
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class _BlockingRuntime:
    def __init__(self) -> None:
        self.release = Event()

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del session_id
        del parts
        del stream
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


def test_cancelled_run_status_is_persisted_to_store(tmp_path: Path) -> None:
    db_path = tmp_path / "run-cancel-integration.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = _BlockingRuntime()
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-cancel-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "cancel"}]},
        headers=_auth_headers("req-cancel-integration-submit"),
    )
    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]

    _wait_for_running(client, run_id)

    cancelled = client.post(
        f"/v1/runs/{run_id}/cancel",
        headers=_auth_headers("req-cancel-integration-cancel"),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    runtime.release.set()

    reloaded_manager = SessionManager(store=SQLiteSessionStore(db_path=db_path))
    entries = reloaded_manager.list_entries(session_id)
    run_statuses = [
        event.data["status"]
        for event in entries
        if event.kind is SessionEntryKind.RUN_STATUS and event.data.get("run_id") == run_id
    ]
    assert run_statuses[-1] == "cancelled"
