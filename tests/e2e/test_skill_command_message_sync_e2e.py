from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.platform.http_api.app import create_app
from nano_multiagent.core.session.manager import SessionManager
from nano_multiagent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class EchoLLMClient:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
            finish_reason="stop",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_sync_message_e2e_rewrites_skill_command_then_runs_runtime(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "skill-command-e2e.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=EchoLLMClient(),
        model="mock-model",
    )
    app = create_app(session_store=store, runtime=runtime, auth_token="test-token")
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-skill-e2e-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "/skill:doc shorten intro"}], "stream": False},
        headers=_auth_headers("req-skill-e2e-message"),
    )

    assert response.status_code == 200
    expected = 'ack:Use the "doc" skill for this request.\nUser input:\nshorten intro'
    assert response.json()["message"]["content"] == expected
