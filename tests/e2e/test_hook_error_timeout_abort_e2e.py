import time
from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.llm.interfaces import LLMGenerateRequest
from nano_multiagent.server.app import create_app
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


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
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-hook-timeout-e2e-run-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_async_timeout_e2e_exposes_run_timeout_hook_and_contract(tmp_path: Path) -> None:
    observed: list[dict[str, object]] = []
    hooks = HookRegistry()

    async def on_run_timeout(event, ctx):
        del ctx
        observed.append(dict(event))

    hooks.on("run_timeout", on_run_timeout)

    store = SQLiteSessionStore(db_path=tmp_path / "hook-timeout-e2e.sqlite3")
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_TimeoutLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
        repo_root=Path.cwd(),
    )

    with TestClient(create_app(session_store=store, runtime=runtime, auth_token="test-token")) as client:
        events_response = client.get(
            "/v1/hooks/events",
            headers=_auth_headers("req-hook-timeout-e2e-events"),
        )
        assert events_response.status_code == 200
        events_payload = {item["event"]: item for item in events_response.json()["events"]}
        assert events_payload["run_timeout"]["mode"] == "observe"
        assert events_payload["run_abort"]["mode"] == "observe"

        created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-hook-timeout-e2e-create"))
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        submitted = client.post(
            f"/v1/sessions/{session_id}/messages:async",
            json={"parts": [{"type": "text", "text": "ping"}]},
            headers=_auth_headers("req-hook-timeout-e2e-submit"),
        )
        assert submitted.status_code == 202
        run_id = submitted.json()["run_id"]

        terminal = _wait_for_terminal_run(client, run_id)
        assert terminal["status"] == "failed"
        assert terminal["stop_reason"] == "timeout"
        assert terminal["error"]["code"] == "run_timeout"

    assert len(observed) == 1
    assert observed[0]["session_id"] == session_id
    assert observed[0]["run_id"] == run_id
