from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.core.agent.runtime import AgentRuntime
from nano_multiagent.core.hooks.registry import HookRegistry
from nano_multiagent.core.hooks.runner import HookRunner
from nano_multiagent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.platform.http_api.app import create_app
from nano_multiagent.core.session.manager import SessionManager
from nano_multiagent.platform.persistence.session.sqlite_store import SQLiteSessionStore


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


def test_hook_query_integration_orders_and_reports_registered_hooks(tmp_path: Path) -> None:
    registry = HookRegistry()

    def first(payload, ctx):
        del payload, ctx
        return {"action": "continue"}

    def second(payload, ctx):
        del payload, ctx
        return {"action": "continue"}

    registry.on(
        "input",
        second,
        source="workspace",
        priority=90,
        timeout_ms=1200,
        module_name="workspace.hooks",
        file_path=tmp_path / ".nano" / "hooks" / "workspace_hook.py",
    )
    registry.on(
        "input",
        first,
        source="builtin",
        priority=10,
        timeout_ms=300,
        module_name="builtin.hooks",
        file_path=tmp_path / "builtin" / "hook.py",
    )

    store = SQLiteSessionStore(db_path=tmp_path / "hooks-query-integration.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=tmp_path,
    )
    client = TestClient(create_app(session_store=store, runtime=runtime, auth_token="test-token"))

    response = client.get("/v1/hooks", headers=_auth_headers("req-hooks-integration"))

    assert response.status_code == 200
    payload = response.json()
    hooks = payload["hooks"]
    assert [item["priority"] for item in hooks] == [10, 90]
    assert hooks[0]["source"] == "builtin"
    assert hooks[0]["mode"] == "intercept"
    assert hooks[1]["source"] == "workspace"
    assert hooks[1]["file_path"].endswith("workspace_hook.py")

    events_response = client.get("/v1/hooks/events", headers=_auth_headers("req-hooks-events-integration"))
    assert events_response.status_code == 200
    names = {item["event"] for item in events_response.json()["events"]}
    assert {"input", "turn_end", "tool_call", "tool_result"}.issubset(names)
