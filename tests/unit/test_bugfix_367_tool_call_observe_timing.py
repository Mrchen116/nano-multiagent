"""bugfix-367: tool_call observe handler 必须在 intercept gate 通过后才 fire.

修复前: loop.py:302 在 LLM 返参后立即触发 observe "tool_call",realtime_stream
        把 tool_start SSE 发出,前端看到 "运行中" —— 但 auto_mode_gate 此时还在 park
        等用户授权,工具根本没开始执行。

修复后: loop.py 不再触发 observe "tool_call";registry.execute 在 intercept gate
        通过后才发同一事件。gate park 期间 observe handler 不会运行;gate deny 时
        observe 也不会运行,前端只在 tool_result 阶段看到 ✕。

这是开发态修复,不做兼容(参见 docs/changes/bugfix-367-permission-history-list/fix.md)。
"""

import asyncio
import pytest

from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.hooks.context import HookContext
from agent.core.hooks.types import HookEventMode
from agent.core.tools.base import Tool, ToolContext
from agent.core.tools.registry import ToolRegistry


pytestmark = pytest.mark.asyncio


class _EchoTool(Tool):
    name = "echo"
    description = "echo back the input"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, context):  # noqa: ANN001
        return {"echoed": args["text"]}


def _build_registry(hooks: HookRegistry) -> ToolRegistry:
    from pathlib import Path
    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

    repo_root = Path("/tmp")
    safety = ToolSafety(repo_root=repo_root, config=ToolSafetyConfig())
    context = ToolContext(repo_root=repo_root, cwd=repo_root, safety=safety)
    runner = HookRunner(registry=hooks)
    registry = ToolRegistry(context=context, hook_runner=runner)
    registry.register(_EchoTool())
    return registry


async def test_observe_tool_call_runs_after_intercept_gate_pass() -> None:
    """gate 通过分支: observe handler 在 gate handler 完成后才 fire,事件名仍是 tool_call."""
    hooks = HookRegistry()
    sequence: list[str] = []

    async def gate_handler(event, ctx):  # noqa: ANN001
        sequence.append("gate")
        # gate 通过(返回 None / 不带 block)

    async def observe_handler(event, ctx):  # noqa: ANN001
        sequence.append(f"observe:{event.get('call_id')}:{event.get('name')}")

    hooks.on("tool_call", gate_handler, priority=20)
    hooks.on("tool_call", observe_handler, priority=1000)

    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-aaa"},
    )
    result = await registry.execute("echo", {"text": "hi"}, hook_context=ctx)
    assert result == {"echoed": "hi"}
    # gate 必须先于 observe;observe payload 带 call_id + name(对齐 realtime_stream 的 SSE 字段)
    assert sequence == ["gate", "observe:call-aaa:echo"], sequence


async def test_observe_tool_call_skipped_when_intercept_gate_blocks() -> None:
    """gate deny 分支: observe handler 不会 fire(intercept 链 break),工具不执行."""
    hooks = HookRegistry()
    sequence: list[str] = []

    async def gate_handler(event, ctx):  # noqa: ANN001
        sequence.append("gate")
        return {"block": True, "reason": "denied by test gate"}

    async def observe_handler(event, ctx):  # noqa: ANN001
        sequence.append("observe")  # 不应被调用

    hooks.on("tool_call", gate_handler, priority=20)
    hooks.on("tool_call", observe_handler, priority=1000)

    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-bbb"},
    )
    from agent.core.errors import ToolError

    with pytest.raises(ToolError) as exc:
        await registry.execute("echo", {"text": "hi"}, hook_context=ctx)
    assert "blocked by hook" in str(exc.value)
    # 关键: observe 没有被调用 —— 前端不会看到 "运行中",决策完成后才在 tool_result 阶段显示 ✕
    assert sequence == ["gate"], sequence


async def test_tool_result_event_carries_arguments_alias() -> None:
    """feat-409 fix 2: the tool_result event must expose ``arguments`` (real args),
    mirroring tool_call — otherwise realtime_stream surfaces input={} on tool_end,
    which clobbers the running entry's input downstream (REST shows {})."""
    hooks = HookRegistry()
    captured: dict[str, object] = {}

    async def observe_result(event, ctx):  # noqa: ANN001
        captured["args"] = event.get("args")
        captured["arguments"] = event.get("arguments")

    hooks.on("tool_result", observe_result, priority=1000)

    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-ccc"},
    )
    await registry.execute("echo", {"text": "hi"}, hook_context=ctx)
    assert captured["arguments"] == {"text": "hi"}
    # 既有 args 键保留(下游/历史可能依赖),arguments 是新增 consumer-facing 别名
    assert captured["args"] == {"text": "hi"}


async def test_loop_no_longer_dispatches_tool_call_observe() -> None:
    """loop._dispatch_tool_call_hook 已删除,loop.py 不再触发 observe 'tool_call'."""
    from agent.core.agent.loop import AgentLoop

    assert not hasattr(AgentLoop, "_dispatch_tool_call_hook"), (
        "loop.py 不应保留 _dispatch_tool_call_hook —— observe 触发责任已迁移至 registry.execute"
    )
