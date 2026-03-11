from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.observability.logger import capture_logs
from agent.platform.http_api.app import create_app
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


class _EchoLLM:
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


def test_observability_chain_e2e_links_trace_with_session_and_turn(tmp_path: Path) -> None:
    hooks = HookRegistry()

    async def explode_on_turn_start(payload, ctx):
        del payload, ctx
        raise RuntimeError("hook-broken")

    hooks.on("turn_start", explode_on_turn_start, source="runtime")

    store = SQLiteSessionStore(db_path=tmp_path / "obs-e2e.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
        repo_root=tmp_path,
    )

    client = TestClient(create_app(session_store=store, runtime=runtime, auth_token="test-token"))

    with capture_logs() as records:
        created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-observ-e2e-create"))
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        response = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"parts": [{"type": "text", "text": "ping"}], "stream": False},
            headers=_auth_headers("req-observ-e2e-message"),
        )

    assert response.status_code == 200
    isolated = [item for item in records if item["message"] == "hook execution isolated"]
    assert isolated
    fields = isolated[0]["fields"]
    assert fields["session_id"] == session_id
    assert isinstance(fields["turn_id"], str)
    assert fields["trace_id"] == "req-observ-e2e-message"
