import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.observability.logger import capture_logs
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService


class _EchoLLM:
    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:  # type: ignore[override]
        yield LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_completed_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-observ-e2e-run-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_observability_chain_e2e_links_trace_with_session_and_turn(tmp_path: Path) -> None:
    hooks = HookRegistry()

    async def explode_on_turn_start(payload, ctx):
        del payload, ctx
        raise RuntimeError("hook-broken")

    hooks.on("turn_start", explode_on_turn_start, source="runtime")

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
        repo_root=tmp_path,
    )

    client = TestClient(create_app(session_store=service.manager._store, runtime=runtime))

    with capture_logs() as records:
        created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-observ-e2e-create"))
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        submitted = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"parts": [{"type": "text", "text": "ping"}]},
            headers=_auth_headers("req-observ-e2e-message"),
        )
        assert submitted.status_code == 200
        run_id = submitted.json()["run_id"]

        _wait_for_completed_run(client, run_id)

    isolated = [item for item in records if item["message"] == "hook execution isolated"]
    assert isolated
    fields = isolated[0]["fields"]
    assert fields["session_id"] == session_id
    assert isinstance(fields["turn_id"], str)
    assert fields["trace_id"] == "req-observ-e2e-message"
