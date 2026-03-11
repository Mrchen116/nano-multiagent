from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)
from agent.core.session.entries import SessionEntryKind
from agent.core.session.manager import SessionManager
from agent.core.session.store import LoadedSession, SessionStore
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.snapshots: dict[str, dict[str, object]] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        session_events = tuple(entry for sid, entry in self.events if sid == session_id)
        if not session_events and session_id not in self.snapshots:
            return None
        return LoadedSession(
            session_id=session_id,
            events=session_events,
            snapshot=self.snapshots.get(session_id),
        )

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        self.snapshots[session_id] = snapshot


class FakeLLMClient:
    def __init__(self, responses: tuple[LLMGenerateResponse, ...] | None = None) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._responses = list(responses) if responses is not None else None

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        if self._responses is None:
            response = LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-pong"),
                finish_reason="stop",
            )
        else:
            if not self._responses:
                raise AssertionError("unexpected llm call")
            response = self._responses.pop(0)
        return LLMGenerateResponse(
            model=request.model,
            message=response.message,
            finish_reason=response.finish_reason,
            raw=response.raw,
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


def test_runtime_run_appends_user_and_assistant_events() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    runtime = AgentRuntime(session_manager=manager, llm_client=FakeLLMClient(), model="mock-model")

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.session_id == session.session_id
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content == "runtime-pong"
    created_event, user_event, assistant_event = [entry for _, entry in store.events]
    assert created_event.kind is SessionEntryKind.SESSION_CREATED
    assert user_event.kind is SessionEntryKind.TURN_APPENDED
    assert user_event.data["role"] == "user"
    assert user_event.data["content"] == "ping"
    assert assistant_event.kind is SessionEntryKind.TURN_APPENDED
    assert assistant_event.data["role"] == "assistant"
    assert assistant_event.data["content"] == "runtime-pong"


def test_runtime_builds_followup_context_from_session_events() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="mock-model")

    runtime.run(session.session_id, [{"type": "text", "text": "first"}], stream=False)
    runtime.run(session.session_id, [{"type": "text", "text": "second"}], stream=False)

    second_call_messages = llm_client.requests[-1].messages
    assert [message.role for message in second_call_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert second_call_messages[1].content == "first"
    assert second_call_messages[2].content == "runtime-pong"
    assert second_call_messages[3].content == "second"


def test_runtime_persists_tool_events_with_metadata_and_replays_context() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_runtime_1",
                            name="echo",
                            arguments={"text": "first"},
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-after-tool"),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-second"),
                finish_reason="stop",
            ),
        )
    )
    runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="mock-model")
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(EchoTool())
    runtime.bind_tool_registry(registry)

    runtime.run(session.session_id, [{"type": "text", "text": "first"}], stream=False)
    runtime.run(session.session_id, [{"type": "text", "text": "second"}], stream=False)

    turn_events = [
        entry
        for _, entry in store.events
        if entry.kind is SessionEntryKind.TURN_APPENDED
    ]
    call_events = [
        entry
        for entry in turn_events
        if entry.data["metadata"].get("tool_phase") == "call"
    ]
    result_events = [
        entry
        for entry in turn_events
        if entry.data["metadata"].get("tool_phase") == "result"
    ]
    assert len(call_events) == 1
    assert len(result_events) == 1
    assert call_events[0].data["role"] == "assistant"
    assert result_events[0].data["role"] == "tool"
    assert call_events[0].data["metadata"]["tool_call_id"] == "call_runtime_1"
    assert result_events[0].data["metadata"]["tool_call_id"] == "call_runtime_1"
    assert call_events[0].data["metadata"]["tool_calls"] == [
        {
            "call_id": "call_runtime_1",
            "name": "echo",
            "arguments": {"text": "first"},
        }
    ]

    second_turn_request = llm_client.requests[-1]
    assert [message.role for message in second_turn_request.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert second_turn_request.messages[2].tool_calls[0].call_id == "call_runtime_1"
    assert second_turn_request.messages[3].tool_call_id == "call_runtime_1"


def test_hook_context_model_call_uses_same_session_id() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content='{"risk":"safe","reason":"read only"}'),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-pong"),
                finish_reason="stop",
            ),
        )
    )
    hooks = HookRegistry()

    def on_input(payload, ctx):  # noqa: ANN001
        _ = ctx.call_model(
            system_prompt="risk-system",
            user_prompt="risk-user",
        )
        return {"action": "continue", "text": payload["text"]}

    hooks.on("input", on_input, priority=10)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
    )

    runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm_client.requests[0].session_id == session.session_id
    assert llm_client.requests[1].session_id == session.session_id


def test_hook_context_model_call_supports_model_override() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="risk-model-x",
                message=LLMMessage(role="assistant", content='{"risk":"safe","reason":"ok"}'),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-pong"),
                finish_reason="stop",
            ),
        )
    )
    hooks = HookRegistry()

    def on_input(payload, ctx):  # noqa: ANN001
        _ = ctx.call_model(
            system_prompt="risk-system",
            user_prompt="risk-user",
            model="risk-model-x",
        )
        return {"action": "continue", "text": payload["text"]}

    hooks.on("input", on_input, priority=10)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
    )

    runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm_client.requests[0].model == "risk-model-x"
    assert llm_client.requests[0].session_id == session.session_id
