import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService


class EchoLLMClient:
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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-skill-e2e-run-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_sync_message_e2e_rewrites_skill_command_then_runs_runtime(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
    )
    app = create_app(session_store=service.manager._store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-skill-e2e-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "/skill:doc shorten intro"}]},
        headers=_auth_headers("req-skill-e2e-message"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    terminal = _wait_for_completed_run(client, run_id)
    assert terminal["status"] == "completed"
    expected = 'ack:Use the "doc" skill for this request.\nUser input:\nshorten intro'
    assert terminal["output_text"] == expected
