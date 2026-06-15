"""bugfix-410-M2 R4: reason_code旁路字段端到端链路 (#82/#97 收口 + denied 来源).

reason_code 是对非成功 tool_call 终态的细化分类，与给模型看的自由文本 reason 并存：
  denied      — 工具被 hook 拒绝（auto block 或用户 Deny），落点 registry.py 的
                blocked_by_hook 收口处
  timed_out   — Gateway 看门狗 cancel（R3 产）
  interrupted — 其他异常终止（R3 产）

本文件覆盖 kernel 侧的链路起点：registry 盖 denied + ToolResult 透传字段。
IM 侧（ToolCall model / 序列化 / 解析）与前端文案另有测试。
"""

from __future__ import annotations

import pytest

from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.core.tools.registry import ToolRegistry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _EchoTool:
    name = "echo"
    description = "echo"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):  # noqa: ANN001, ANN201
        del ctx
        return {"echoed": args["text"]}


def _build_registry(hooks: HookRegistry) -> ToolRegistry:
    context = ToolContext.create(repo_root=__import__("pathlib").Path.cwd())
    runner = HookRunner(registry=hooks)
    registry = ToolRegistry(context=context, hook_runner=runner)
    registry.register(_EchoTool())
    return registry


async def test_blocked_tool_carries_reason_code_denied() -> None:
    """A hook-blocked tool_call must raise ToolError whose details carry a dedicated
    reason_code='denied', kept SEPARATE from the model-facing free-text reason."""
    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": True, "reason": "no permission channel available"}

    hooks.on("tool_call", gate, priority=20)
    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-1"},
    )

    with pytest.raises(ToolError) as exc:
        await registry.execute("echo", {"text": "hi"}, hook_context=ctx)

    details = exc.value.details
    assert details.get("reason_code") == "denied", (
        "blocked tool must carry reason_code='denied' for badge classification"
    )
    # The model-facing free-text reason is preserved and NOT overwritten by the code.
    assert details.get("reason") == "no permission channel available"


async def test_tool_result_propagates_reason_code_from_tool_error() -> None:
    """The executor must lift reason_code out of a ToolError into the ToolResult so
    downstream event translation can forward it (#82/#97 badge reason chain)."""
    from agent.core.agent.tool_executor import StreamingToolExecutor
    from agent.core.types import ToolCall

    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": True, "reason": "denied by gate"}

    hooks.on("tool_call", gate, priority=20)
    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-2"},
    )

    executor = StreamingToolExecutor(registry, hook_context=ctx)
    executor.add_tool(ToolCall(call_id="call-2", name="echo", arguments={"text": "hi"}))
    results = [r async for r in executor.get_remaining_results()]

    assert len(results) == 1
    result = results[0]
    assert result.error is not None
    assert result.reason_code == "denied", (
        "ToolResult must surface reason_code so loop/stream can forward the badge reason"
    )
