import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.platform.hooks.loader import build_hook_registry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService


class _EchoLLM:
    async def generate(self, request: LLMGenerateRequest):  # noqa: ANN201
        last_content = request.messages[-1].content
        yield LLMMessage(role="assistant", content=f"ack:{last_content}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-sse-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_session_run_completes_and_messages_are_visible(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    client = TestClient(create_app(session_store=service.manager.store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "stream me"}]},
        headers=_auth_headers("req-sse-integration-submit"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"

    messages_response = client.get(
        f"/v1/sessions/{session_id}/messages",
        headers=_auth_headers("req-sse-integration-messages"),
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert any(m["role"] == "assistant" and "ack:" in m["content"] for m in messages)


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

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    runtime = AgentRuntime(
        session_manager=service.manager,
        llm_client=_EchoLLM(),
        model="mock-model",
        hook_runner=HookRunner(registry=build_hook_registry(repo_root=tmp_path)),
        repo_root=tmp_path,
    )
    client = TestClient(create_app(session_store=service.manager.store, runtime=runtime))

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-sse-integration-consistency-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    submitted = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "stream me"}]},
        headers=_auth_headers("req-sse-integration-consistency-submit"),
    )
    assert submitted.status_code == 200
    run_id = submitted.json()["run_id"]

    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"

    # Verify the turn was persisted under the real session_id (not spoofed)
    entries = service.manager.list_entries(session_id)
    turn_events = [e for e in entries if e.kind is SessionEntryKind.TURN_APPENDED]
    assert any(e.session_id == session_id for e in turn_events)
    assert all(e.session_id != "spoofed_session" for e in turn_events)
