from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.platform.hooks.loader import build_hook_registry
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
            finish_reason="completed",
        )


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_session_sse_stream_contains_async_run_events(tmp_path: Path) -> None:
    db_path = tmp_path / "sse-session-stream.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "stream me"}]},
        headers=_auth_headers("req-sse-integration-submit"),
    )
    assert submitted.status_code == 202

    response = client.get(
        f"/v1/sessions/{session_id}/events?max_events=8&timeout_seconds=0.2",
        headers=_auth_headers("req-sse-integration-events"),
    )

    assert response.status_code == 200
    body = response.text
    assert "event: run_status" in body
    assert '"status":"completed"' in body
    assert "event: text_delta" in body
    assert "event: turn_end" in body


def test_hook_context_publish_session_event_enforces_current_session_id(tmp_path: Path) -> None:
    hooks_dir = tmp_path / ".nano" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "spoof_session_id.py").write_text(
        "\n".join(
            [
                "def setup(hooks):",
                "    async def on_message_update(event, ctx):",
                "        ctx.publish_session_event(",
                "            event='custom_publish',",
                "            data={",
                "                'session_id': 'spoofed_session',",
                "                'run_id': event.get('run_id'),",
                "            },",
                "        )",
                "    hooks.on('message_update', on_message_update, priority=900, timeout_ms=500)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    db_path = tmp_path / "sse-session-stream-consistency.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    client = TestClient(create_app(session_store=store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-integration-consistency-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages:async",
        json={"parts": [{"type": "text", "text": "stream me"}]},
        headers=_auth_headers("req-sse-integration-consistency-submit"),
    )
    assert submitted.status_code == 202

    response = client.get(
        f"/v1/sessions/{session_id}/events?max_events=20&timeout_seconds=0.2",
        headers=_auth_headers("req-sse-integration-consistency-events"),
    )
    assert response.status_code == 200
    body = response.text
    assert "event: custom_publish" in body
    assert f"\"session_id\":\"{session_id}\"" in body
    assert "spoofed_session" not in body
