import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService

# Fixture replaces deleted _FIXTURE_WITH_PLACEHOLDERS (segment assembly now owns this content).
_FIXTURE_WITH_PLACEHOLDERS = (
    "You are an expert coding assistant.\n\n"
    "Available tools:\n<RUNTIME_FILL:AVAILABLE_TOOLS>\n\n"
    "Guidelines:\n- Be helpful\n\n"
    "Current date and time: <RUNTIME_FILL:CURRENT_DATETIME>\n"
    "Current working directory: <RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>"
)


class CapturePromptLLM:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:  # type: ignore[override]
        self.requests.append(request)
        yield LLMMessage(role="assistant", content="ok")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_completed_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-system-prompt-run-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_message_sync_e2e_renders_runtime_system_prompt(tmp_path: Path) -> None:
    llm = CapturePromptLLM()
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    # _FIXTURE_WITH_PLACEHOLDERS injected so "Guidelines:" and placeholders are present.
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
        system_prompt=_FIXTURE_WITH_PLACEHOLDERS,
    )
    app = create_app(session_store=service.manager._store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={"workspace_root": str(tmp_path)}, headers=_auth_headers("req-system-prompt-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}]},
        headers=_auth_headers("req-system-prompt-message"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    terminal = _wait_for_completed_run(client, run_id)
    assert terminal["status"] == "completed"
    assert terminal["output_text"] == "ok"

    assert llm.requests, "no LLM requests captured"
    system_prompt = llm.requests[-1].messages[0].content
    assert "Guidelines:" in system_prompt
    assert "Current date and time:" in system_prompt
    assert f"Current working directory: {tmp_path}" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt
