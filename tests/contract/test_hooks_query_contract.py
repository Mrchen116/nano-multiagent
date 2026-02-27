from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.server.app import create_app
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


class _LLMStub:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
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


def _build_client(tmp_path: Path) -> TestClient:
    registry = HookRegistry()

    def on_input(payload, ctx):
        del payload, ctx
        return {"action": "continue"}

    registry.on(
        "input",
        on_input,
        source="runtime",
        module_name="runtime.hooks",
        file_path=tmp_path / "runtime_hook.py",
        priority=15,
        timeout_ms=800,
    )

    store = SQLiteSessionStore(db_path=tmp_path / "hooks-query-contract.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_LLMStub(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=tmp_path,
    )
    app = create_app(session_store=store, runtime=runtime, auth_token="test-token")
    return TestClient(app)


def test_hook_events_contract_shape() -> None:
    client = _build_client(Path.cwd())

    response = client.get("/v1/hooks/events", headers=_auth_headers("req-hooks-events-contract"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-hooks-events-contract"
    payload = response.json()
    assert set(payload.keys()) == {"events"}
    assert isinstance(payload["events"], list)
    assert payload["events"]

    first = payload["events"][0]
    assert set(first.keys()) == {"event", "mode", "return_contract"}


def test_hooks_registry_contract_shape() -> None:
    client = _build_client(Path.cwd())

    response = client.get("/v1/hooks", headers=_auth_headers("req-hooks-list-contract"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-hooks-list-contract"
    payload = response.json()
    assert set(payload.keys()) == {"hooks"}
    assert isinstance(payload["hooks"], list)
    assert payload["hooks"]

    first = payload["hooks"][0]
    assert set(first.keys()) == {
        "hook_id",
        "event",
        "mode",
        "source",
        "module_name",
        "file_path",
        "priority",
        "timeout_ms",
    }
