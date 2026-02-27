import time
from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.server.app import create_app
from nano_multiagent.session.entries import SessionEntryKind
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class _EchoLLM:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
            finish_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 1.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-runs-store-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_async_run_status_entries_persist_in_sqlite_store(tmp_path: Path) -> None:
    db_path = tmp_path / "runs-store.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_EchoLLM(),
        model="mock-model",
    )
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-store-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "persist me"}]},
        headers=_auth_headers("req-runs-store-submit"),
    )
    assert submitted.status_code == 202

    run_id = submitted.json()["run_id"]
    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"

    reloaded_store = SQLiteSessionStore(db_path=db_path)
    reloaded_manager = SessionManager(store=reloaded_store)
    entries = reloaded_manager.list_entries(session_id)
    run_events = [
        event
        for event in entries
        if isinstance(event.data, dict)
        and event.kind is SessionEntryKind.RUN_STATUS
        and event.data.get("run_id") == run_id
    ]

    assert [event.data["status"] for event in run_events] == ["queued", "running", "completed"]
