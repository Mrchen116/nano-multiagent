import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService


class _TimeoutLLM:
    def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        del request
        raise TimeoutError("upstream timeout")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 1.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-hook-critical-run-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_shutdown_emits_session_shutdown_hook_on_app_close(tmp_path: Path) -> None:
    observed: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_session_shutdown(event, ctx):
        del ctx
        observed.append(dict(event))

    hooks.on("session_shutdown", on_session_shutdown)

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions-shutdown"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_TimeoutLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
        repo_root=tmp_path,
    )

    with TestClient(create_app(session_store=service.manager.store, runtime=runtime)) as client:
        created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-hook-critical-create"))
        assert created.status_code == 201
        session_id = created.json()["session_id"]

    assert observed == [{"session_id": session_id}]


def test_async_timeout_emits_run_timeout_hook(tmp_path: Path) -> None:
    observed: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_run_timeout(event, ctx):
        del ctx
        observed.append(dict(event))

    hooks.on("run_timeout", on_run_timeout)

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions-timeout"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_TimeoutLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
        repo_root=tmp_path,
    )

    with TestClient(create_app(session_store=service.manager.store, runtime=runtime)) as client:
        created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-hook-critical-timeout-create"))
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        submitted = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"parts": [{"type": "text", "text": "ping"}]},
            headers=_auth_headers("req-hook-critical-timeout-submit"),
        )
        assert submitted.status_code == 200
        run_id = submitted.json()["run_id"]

        terminal = _wait_for_terminal_run(client, run_id)
        assert terminal["status"] == "failed"
        assert terminal["error"]["code"] == "run_timeout"

    assert len(observed) == 1
    assert observed[0]["session_id"] == session_id
    assert observed[0]["run_id"] == run_id
