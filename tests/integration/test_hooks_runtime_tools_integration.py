import asyncio
from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.platform.hooks.loader import load_hooks_from_directories
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest):  # AsyncIterator[LLMMessage]
        self.requests.append(request)
        # Yield assistant content, then terminal metadata with finish_reason.
        yield LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


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


async def test_runtime_uses_loaded_hooks_for_input_transform_chain(tmp_path: Path) -> None:
    builtins_dir = tmp_path / "builtin_hooks"
    workspace_dir = tmp_path / ".nano" / "hooks"
    builtins_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    (builtins_dir / "prefix.py").write_text(
        """
def setup(hooks):
    async def on_input(event, ctx):
        del ctx
        return {"action": "transform", "text": f"builtin:{event['text']}"}
    hooks.on("input", on_input, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "suffix.py").write_text(
        """
def setup(hooks):
    async def on_input(event, ctx):
        del ctx
        return {"action": "transform", "text": f"{event['text']}:workspace"}
    hooks.on("input", on_input, priority=100)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    hook_registry, loaded = load_hooks_from_directories(
        repo_root=tmp_path,
        builtins_dir=builtins_dir,
        workspace_dir=workspace_dir,
    )
    assert len(loaded) == 2

    manager = SessionManager(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    session = manager.create_session(workspace_root=tmp_path)
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=hook_registry),
        repo_root=tmp_path,
    )

    result = await runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm.requests[-1].messages[-1].content == "builtin:ping:workspace"
    assert result.messages[0].content == "ack:builtin:ping:workspace"


def test_tool_registry_uses_loaded_hooks_for_block_and_rewrite(tmp_path: Path) -> None:
    # Use HookRegistry directly to avoid loading auto_mode_gate builtin
    # (which would block 'echo' since it's not in SAFE_TOOL_ALLOWLIST).
    from agent.core.hooks.registry import HookRegistry as _HookRegistry

    hook_registry = _HookRegistry()

    async def on_tool_call(event, ctx):
        del ctx
        if event["name"] == "echo" and event["args"].get("text") == "blocked":
            return {"block": True, "reason": "workspace-policy"}
        return {"block": False}

    async def on_tool_result(event, ctx):
        del ctx
        if event["name"] == "echo":
            return {"content": {"text": f"rewritten:{event['output']['text']}"}}
        return None

    hook_registry.on("tool_call", on_tool_call, priority=100)
    hook_registry.on("tool_result", on_tool_result, priority=100)

    runner = HookRunner(registry=hook_registry)
    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=runner,
    )
    tool_registry.register(EchoTool())

    with pytest.raises(ToolError, match="blocked by hook"):
        asyncio.run(tool_registry.execute(
            "echo",
            {"text": "blocked"},
            hook_context=HookContext(session_id="sess_tool_block", repo_root=tmp_path),
        ))

    rewritten = asyncio.run(tool_registry.execute(
        "echo",
        {"text": "ping"},
        hook_context=HookContext(session_id="sess_tool_rewrite", repo_root=tmp_path),
    ))
    assert rewritten == {"text": "rewritten:ping"}
