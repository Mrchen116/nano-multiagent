import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMMessage,
    LLMToolCall,
)
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry
from collections.abc import AsyncIterator


class EchoLLMClient:
    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        last_user = request.messages[-1].content
        yield LLMMessage(role="assistant", content=f"ack:{last_user}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


class ToolCallingLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.calls += 1
        if self.calls == 1:
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="call_integration_1",
                        name="echo",
                        arguments={"text": "integration-tool"},
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
        else:
            yield LLMMessage(role="assistant", content="tool-finished")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")


class EchoTool:
    name = "echo"
    description = "echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):  # noqa: ANN001, ANN201
        del ctx
        return {"echoed": args["text"]}


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def _wait_for_terminal_run(client: TestClient, run_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=_auth_headers("req-run-get"))
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach terminal status before timeout")


def test_message_route_calls_runtime_and_persists_turn_events(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
    )
    app = create_app(session_store=service.manager.store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "integration"}]},
        headers=_auth_headers("req-integration-message"),
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-integration-message"
    run_id = response.json()["run_id"]

    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"

    turn_events = [e for e in manager.list_entries(session_id) if e.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 2
    assert turn_events[0].data["role"] == "user"
    assert turn_events[0].data["content"] == "integration"
    assert turn_events[1].data["role"] == "assistant"
    assert turn_events[1].data["content"] == "ack:integration"


def test_message_route_wires_runtime_with_real_tool_registry(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
    )
    app = create_app(session_store=service.manager.store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-integration-tool-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "wiring-check"}]},
        headers=_auth_headers("req-integration-tool-message"),
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    terminal = _wait_for_terminal_run(client, run_id)
    assert terminal["status"] == "completed"

    turn_events = [e for e in manager.list_entries(session_id) if e.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 2
    assert turn_events[0].data["role"] == "user"
    assert turn_events[1].data["role"] == "assistant"
    assert "wiring-check" in turn_events[1].data["content"]
