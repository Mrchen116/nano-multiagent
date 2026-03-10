import time
from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.errors import ModelError
from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.platform.http_api.app import create_app
from nano_multiagent.core.session.entries import SessionEntryKind
from nano_multiagent.core.session.manager import SessionManager
from nano_multiagent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class _EchoLLM:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
            finish_reason="completed",
        )


class _RetryThenSuccessRuntime:
    def __init__(self, *, fail_times: int) -> None:
        self._fail_times = fail_times
        self.calls = 0

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None):  # noqa: ANN001, ANN201
        del parts, stream, run_id
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ModelError(f"upstream flaky #{self.calls}", retryable=True)
        return TurnResult(
            session_id=session_id,
            turn_id="turn_async_retry_store",
            messages=(Message(message_id="msg_async_retry_store", role="assistant", content="ok"),),
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


def test_async_run_persists_retry_metadata_during_retryable_failures(tmp_path: Path, monkeypatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "nano_multiagent.runs.registry._wait_with_cancel",
        lambda _event, seconds: sleep_calls.append(seconds) or False,
    )

    db_path = tmp_path / "runs-store-retry.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = _RetryThenSuccessRuntime(fail_times=5)
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-store-retry-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "persist retry"}]},
        headers=_auth_headers("req-runs-store-retry-submit"),
    )
    assert submitted.status_code == 202

    run_id = submitted.json()["run_id"]
    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"
    assert sleep_calls == [0.5, 1.0, 2.0, 0.5, 1.0, 30.0]

    reloaded_store = SQLiteSessionStore(db_path=db_path)
    reloaded_manager = SessionManager(store=reloaded_store)
    entries = reloaded_manager.list_entries(session_id)
    retry_events = [
        event
        for event in entries
        if event.kind is SessionEntryKind.RUN_STATUS
        and event.data.get("run_id") == run_id
        and event.data.get("status") == "running"
        and event.data.get("attempt") is not None
    ]
    assert [event.data["attempt"] for event in retry_events] == [1, 2, 3, 4, 5]
    assert [event.data["next_delay"] for event in retry_events] == [0.5, 1.0, 2.0, 0.5, 1.0]
    assert retry_events[-1].data["cooldown"] == 30.0
