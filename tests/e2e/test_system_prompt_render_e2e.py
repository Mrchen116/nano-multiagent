from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.prompting import CODING_SYSTEM_PROMPT
from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.server.app import create_app
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class CapturePromptLLM:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="ok"),
            finish_reason="stop",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_message_sync_e2e_renders_runtime_system_prompt(tmp_path: Path) -> None:
    llm = CapturePromptLLM()
    store = SQLiteSessionStore(db_path=tmp_path / "prompt-e2e.sqlite3")
    # CODING_SYSTEM_PROMPT injected so "Guidelines:" and placeholders are present.
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
        system_prompt=CODING_SYSTEM_PROMPT,
    )
    app = create_app(session_store=store, runtime=runtime, auth_token="test-token")
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-system-prompt-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "ping"}], "stream": False},
        headers=_auth_headers("req-system-prompt-message"),
    )
    assert response.status_code == 200
    assert response.json()["message"]["content"] == "ok"

    system_prompt = llm.requests[-1].messages[0].content
    assert "Guidelines:" in system_prompt
    assert "Current date and time:" in system_prompt
    assert f"Current working directory: {tmp_path}" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt

