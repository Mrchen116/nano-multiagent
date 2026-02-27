from pathlib import Path

import pytest

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.core.errors import ToolError
from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from nano_multiagent.session.manager import SessionManager
from nano_multiagent.session.stores.base import LoadedSession, SessionStore
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


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


class StubLLMClient:
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        del request
        return LLMGenerateResponse(
            model="mock-model",
            message=LLMMessage(role="assistant", content="ignored"),
            finish_reason="stop",
        )


class EchoTool:
    name = "echo"
    description = "Echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        del ctx
        return {"text": args["text"]}


def test_runtime_input_handled_short_circuit_contract() -> None:
    registry = HookRegistry()

    async def handled(event, ctx):
        del event, ctx
        return {"action": "handled"}

    registry.on("input", handled)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=StubLLMClient(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.completed is True
    assert result.stop_reason == "handled_by_hook"
    assert result.messages == ()


def test_tool_call_block_error_contract() -> None:
    registry = HookRegistry()

    async def block(event, ctx):
        del event, ctx
        return {"block": True, "reason": "policy"}

    registry.on("tool_call", block)

    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=HookRunner(registry=registry),
    )
    tool_registry.register(EchoTool())

    with pytest.raises(ToolError) as exc_info:
        tool_registry.execute(
            "echo",
            {"text": "ping"},
            hook_context=HookContext(session_id="sess_contract", repo_root=Path.cwd()),
        )

    assert exc_info.value.tool_name == "echo"
    assert exc_info.value.details == {"blocked_by_hook": True, "reason": "policy"}


def test_tool_result_rewrite_contract() -> None:
    registry = HookRegistry()

    async def rewrite(event, ctx):
        del event, ctx
        return {"content": {"text": "rewritten-by-hook"}, "details": {"source": "hook"}, "is_error": False}

    registry.on("tool_result", rewrite)

    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=HookRunner(registry=registry),
    )
    tool_registry.register(EchoTool())

    result = tool_registry.execute(
        "echo",
        {"text": "ping"},
        hook_context=HookContext(session_id="sess_contract", repo_root=Path.cwd()),
    )

    assert result == {"text": "rewritten-by-hook"}

