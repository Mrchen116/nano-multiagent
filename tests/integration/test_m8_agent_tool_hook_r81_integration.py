from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
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


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}"),
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

    def __init__(self) -> None:
        self.calls = 0

    def run(self, args, ctx):
        del ctx
        self.calls += 1
        return {"text": args["text"]}


def _runtime_with_hooks(registry: HookRegistry) -> tuple[AgentRuntime, EchoLLMClient, SessionManager, str]:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )
    return runtime, llm, manager, session.session_id


def _tool_registry_with_hooks(registry: HookRegistry) -> tuple[ToolRegistry, EchoTool]:
    tool = EchoTool()
    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=HookRunner(registry=registry),
    )
    tool_registry.register(tool)
    return tool_registry, tool


def test_runtime_input_transform_and_handled_are_effective() -> None:
    registry = HookRegistry()

    async def transform_input(event, ctx):
        del ctx
        return {"action": "transform", "text": f"rewritten:{event['text']}"}

    async def handled_input(event, ctx):
        del event, ctx
        return {"action": "handled"}

    async def before_agent_start(event, ctx):
        del event, ctx
        pytest.fail("before_agent_start should not run when input hook handled")

    registry.on("input", transform_input, priority=10)
    registry.on("input", handled_input, priority=20)
    registry.on("before_agent_start", before_agent_start, priority=10)

    runtime, llm, manager, session_id = _runtime_with_hooks(registry)

    result = runtime.run(session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.stop_reason == "handled_by_hook"
    assert result.messages == ()
    assert llm.requests == []
    assert len(manager.list_turn_messages(session_id)) == 0


def test_tool_call_block_is_applied_before_tool_execution_and_arg_validation() -> None:
    registry = HookRegistry()

    async def block_call(event, ctx):
        del ctx
        if event["name"] == "echo":
            return {"block": True, "reason": "policy"}
        return {"block": False}

    registry.on("tool_call", block_call, priority=10)
    tool_registry, tool = _tool_registry_with_hooks(registry)

    with pytest.raises(ToolError, match="blocked by hook") as exc_info:
        tool_registry.execute(
            "echo",
            {},
            hook_context=HookContext(session_id="sess-r81-block", repo_root=Path.cwd()),
        )

    assert exc_info.value.details["blocked_by_hook"] is True
    assert exc_info.value.details["reason"] == "policy"
    assert tool.calls == 0


def test_tool_result_rewrite_output_is_applied_before_return() -> None:
    registry = HookRegistry()

    async def rewrite_result(event, ctx):
        del ctx
        if event["name"] == "echo":
            return {"output": {"text": f"rewritten:{event['output']['text']}"}}
        return None

    registry.on("tool_result", rewrite_result, priority=10)
    tool_registry, _ = _tool_registry_with_hooks(registry)

    result = tool_registry.execute(
        "echo",
        {"text": "ping"},
        hook_context=HookContext(session_id="sess-r81-rewrite", repo_root=Path.cwd()),
    )

    assert result == {"text": "rewritten:ping"}


def test_tool_result_rewrite_list_content_is_passthrough() -> None:
    registry = HookRegistry()

    async def rewrite_result(event, ctx):
        del event, ctx
        return {
            "content": [
                {"type": "text", "text": "part-a"},
                {"type": "image", "image_url": "data:image/png;base64,xxx"},
            ]
        }

    registry.on("tool_result", rewrite_result, priority=10)
    tool_registry, _ = _tool_registry_with_hooks(registry)

    result = tool_registry.execute(
        "echo",
        {"text": "ping"},
        hook_context=HookContext(session_id="sess-r81-list-content", repo_root=Path.cwd()),
    )

    assert result == {
        "content": [
            {"type": "text", "text": "part-a"},
            {"type": "image", "image_url": "data:image/png;base64,xxx"},
        ]
    }


def test_hook_exceptions_are_isolated_and_fail_open_for_runtime_and_tools() -> None:
    runtime_registry = HookRegistry()

    async def runtime_exploding(event, ctx):
        del event, ctx
        raise RuntimeError("runtime boom")

    runtime_registry.on("input", runtime_exploding, priority=10)
    runtime, llm, _, session_id = _runtime_with_hooks(runtime_registry)
    runtime_result = runtime.run(session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert runtime_result.messages[0].content == "ack:ping"
    assert llm.requests[-1].messages[-1].content == "ping"

    tools_registry = HookRegistry()

    async def tools_exploding(event, ctx):
        del event, ctx
        raise RuntimeError("tool boom")

    tools_registry.on("tool_result", tools_exploding, priority=10)
    tool_registry, tool = _tool_registry_with_hooks(tools_registry)

    tool_result = tool_registry.execute(
        "echo",
        {"text": "pong"},
        hook_context=HookContext(session_id="sess-r81-fail-open", repo_root=Path.cwd()),
    )

    assert tool_result == {"text": "pong"}
    assert tool.calls == 1
