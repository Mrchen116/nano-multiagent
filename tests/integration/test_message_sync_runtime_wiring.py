from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)
from nano_multiagent.server.app import create_app
from nano_multiagent.session.entries import SessionEntryKind
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


class EchoLLMClient:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        last_user = request.messages[-1].content
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{last_user}"),
            finish_reason="stop",
        )


class ToolCallingLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.calls += 1
        if self.calls == 1:
            return LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_integration_1",
                            name="echo",
                            arguments={"text": "integration-tool"},
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            )
        assert request.messages[-1].role == "tool"
        assert request.messages[-1].tool_call_id == "call_integration_1"
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content="tool-finished"),
            finish_reason="stop",
        )


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


def test_message_route_calls_runtime_and_persists_turn_events(tmp_path: Path) -> None:
    db_path = tmp_path / "message-sync.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=EchoLLMClient(),
        model="mock-model",
    )
    app = create_app(session_store=store, runtime=runtime)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-integration-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "integration"}], "stream": False},
        headers=_auth_headers("req-integration-message"),
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-integration-message"
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["message"]["content"] == "ack:integration"

    loaded = store.load_session(session_id)
    assert loaded is not None
    turn_events = [event for event in loaded.events if event.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 2
    assert turn_events[0].data["role"] == "user"
    assert turn_events[0].data["content"] == "integration"
    assert turn_events[1].data["role"] == "assistant"
    assert turn_events[1].data["content"] == "ack:integration"


def test_message_route_wires_runtime_with_real_tool_registry(tmp_path: Path) -> None:
    db_path = tmp_path / "message-sync-tools.sqlite3"
    store = SQLiteSessionStore(db_path=db_path)
    runtime = AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=ToolCallingLLMClient(),
        model="mock-model",
    )
    tool_registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    tool_registry.register(EchoTool())
    app = create_app(session_store=store, runtime=runtime, tool_registry=tool_registry)
    client = TestClient(app)

    created = client.post("/v1/sessions", json={}, headers=_auth_headers("req-integration-tool-create"))
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"parts": [{"type": "text", "text": "integration-tool"}], "stream": False},
        headers=_auth_headers("req-integration-tool-message"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["message"]["content"] == "tool-finished"

    loaded = store.load_session(session_id)
    assert loaded is not None
    turn_events = [event for event in loaded.events if event.kind is SessionEntryKind.TURN_APPENDED]
    call_events = [
        event
        for event in turn_events
        if event.data["metadata"].get("tool_phase") == "call"
    ]
    result_events = [
        event
        for event in turn_events
        if event.data["metadata"].get("tool_phase") == "result"
    ]
    assert len(call_events) == 1
    assert len(result_events) == 1
    assert call_events[0].data["metadata"]["tool_call_id"] == "call_integration_1"
    assert result_events[0].data["metadata"]["tool_call_id"] == "call_integration_1"
