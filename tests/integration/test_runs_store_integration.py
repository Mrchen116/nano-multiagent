import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ModelError
from agent.core.types import Message, TurnResult
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService


class _EchoLLM:
    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        yield LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class _RetryThenSuccessRuntime:
    def __init__(self, *, fail_times: int) -> None:
        self._fail_times = fail_times
        self.calls = 0

    def run(self, session_id: str, parts, *, stream: bool = True, run_id: str | None = None, controller=None, origin=None, workspace_root=None):  # noqa: ANN001, ANN201
        del parts, stream, run_id, origin, workspace_root
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


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-runs-store-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_async_run_completes_and_is_visible_via_api(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_EchoLLM(),
        model="mock-model",
    )
    client = TestClient(create_app(session_store=service.manager.store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-store-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "persist me"}]},
        headers=_auth_headers("req-runs-store-submit"),
    )
    assert submitted.status_code == 200

    run_id = submitted.json()["run_id"]
    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"


def test_async_run_fails_when_runtime_raises_model_error(tmp_path: Path) -> None:
    # RunsRegistry executes each run once; retryable ModelError from the runtime
    # layer is treated as terminal (retries happen inside AgentLoop, not here).
    runtime = _RetryThenSuccessRuntime(fail_times=999)
    client = TestClient(
        create_app(runtime=runtime, session_store=JsonlSessionStore(data_dir=tmp_path))
    )

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-runs-store-retry-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "persist retry"}]},
        headers=_auth_headers("req-runs-store-retry-submit"),
    )
    assert submitted.status_code == 200

    run_id = submitted.json()["run_id"]
    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "failed"
