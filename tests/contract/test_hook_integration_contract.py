from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry


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


def test_runtime_input_handled_short_circuit_contract(tmp_path: Path) -> None:
    registry = HookRegistry()

    async def handled(event, ctx):
        del event, ctx
        return {"action": "handled"}

    registry.on("input", handled)

    manager = SessionManager(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    session = manager.create_session(workspace_root=tmp_path)
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

    assert exc_info.value.details == {
        "blocked_by_hook": True,
        "reason": "policy",
        "tool_name": "echo",
    }


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


def test_tool_result_rewrite_list_content_contract() -> None:
    registry = HookRegistry()

    async def rewrite(event, ctx):
        del event, ctx
        return {"content": [{"type": "text", "text": "part-a"}, {"type": "image", "image_url": "data:image/png;base64,xxx"}]}

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

    assert result == {
        "content": [
            {"type": "text", "text": "part-a"},
            {"type": "image", "image_url": "data:image/png;base64,xxx"},
        ]
    }
