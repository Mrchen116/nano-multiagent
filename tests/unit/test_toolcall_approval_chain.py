"""feat-434-M1: approval 旁路字段端到端链路（内核段）.

approval 标识「某次工具调用是否经用户卡决策」，与 reason_code（非成功终态分类）
正交并存：
  user_allow — 用户在权限卡点了允许/本会话允许/总是允许，工具成功放行
  user_deny  — 用户点了拒绝
  None       — 自动放行 / 自动 block / 普通无需授权的工具（闸门区不显）

deny 侧与现成 reason_code=denied 同源（ToolError.details），allow 侧无现成载体，
须新建传播链：gate 返回信号 → runner block=False 保留 → registry 成功路径 lift →
ToolResult.approval → realtime_stream tool_end 携带。本文件覆盖这条链的内核起点。
IM/Gateway/前端段另有测试。
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


# ---------------------------------------------------------------------------
# runner: block=False 分支必须保留 approval（allow 链最易漏的一环）
# ---------------------------------------------------------------------------


async def test_runner_block_false_preserves_approval() -> None:
    """tool_call hook 返回 {block:False, approval:"user_allow"} 时，runner 合并分支
    必须保留 approval；现状 block=False 只留 args/allow_unlisted，会把 approval 丢掉。"""
    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": False, "approval": "user_allow"}

    hooks.on("tool_call", gate, priority=20)
    runner = HookRunner(registry=hooks)
    ctx = HookContext(session_id="s-1", repo_root=None, metadata={})

    dispatch = await runner.dispatch_intercept(
        "tool_call", {"name": "echo", "args": {"text": "hi"}, "block": False}, ctx
    )
    assert dispatch.payload.get("approval") == "user_allow", (
        "runner block=False 分支必须把 approval 透传出来，否则 allow 标识传不到 registry"
    )


async def test_runner_block_false_no_approval_stays_absent() -> None:
    """自动放行（gate 不返回 approval）→ payload 无 approval，保持 None 语义。"""
    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": False}

    hooks.on("tool_call", gate, priority=20)
    runner = HookRunner(registry=hooks)
    ctx = HookContext(session_id="s-1", repo_root=None, metadata={})

    dispatch = await runner.dispatch_intercept(
        "tool_call", {"name": "echo", "args": {"text": "hi"}, "block": False}, ctx
    )
    assert dispatch.payload.get("approval") is None


# ---------------------------------------------------------------------------
# registry + tool_executor: allow 成功路径 lift approval 到 ToolResult
# ---------------------------------------------------------------------------


async def test_allowed_tool_result_carries_user_allow() -> None:
    """gate allow（block=False + approval=user_allow）→ 工具成功执行 →
    ToolResult.approval == "user_allow"。这是退出标准的核心：allow 成功也要标。"""
    from agent.core.agent.tool_executor import StreamingToolExecutor
    from agent.core.types import ToolCall

    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": False, "approval": "user_allow"}

    hooks.on("tool_call", gate, priority=20)
    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-allow"},
    )

    executor = StreamingToolExecutor(registry, hook_context=ctx)
    executor.add_tool(
        ToolCall(call_id="call-allow", name="echo", arguments={"text": "hi"})
    )
    results = [r async for r in executor.get_remaining_results()]

    assert len(results) == 1
    result = results[0]
    assert result.error is None, "allow 工具应成功执行"
    assert result.approval == "user_allow", (
        "成功放行的 ToolResult 必须带 approval=user_allow（allow 侧无 reason_code 载体，须新填）"
    )
    # 成功工具无非成功终态分类
    assert result.reason_code is None


async def test_auto_allowed_tool_result_has_no_approval() -> None:
    """自动放行（gate block=False 不返回 approval）→ ToolResult.approval is None。
    闸门区只标真正经用户卡决策的，自动放行不标。"""
    from agent.core.agent.tool_executor import StreamingToolExecutor
    from agent.core.types import ToolCall

    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": False}

    hooks.on("tool_call", gate, priority=20)
    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-auto"},
    )

    executor = StreamingToolExecutor(registry, hook_context=ctx)
    executor.add_tool(
        ToolCall(call_id="call-auto", name="echo", arguments={"text": "hi"})
    )
    results = [r async for r in executor.get_remaining_results()]

    assert results[0].approval is None


# ---------------------------------------------------------------------------
# deny 侧: approval=user_deny 与 reason_code=denied 同源（ToolError.details）
# ---------------------------------------------------------------------------


async def test_denied_tool_carries_user_deny_approval() -> None:
    """用户 Deny → gate block=True + approval=user_deny → registry raise ToolError，
    details 同时携带 reason_code=denied 与 approval=user_deny。"""
    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": True, "reason": "user denied", "approval": "user_deny"}

    hooks.on("tool_call", gate, priority=20)
    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-deny"},
    )

    with pytest.raises(ToolError) as exc:
        await registry.execute("echo", {"text": "hi"}, hook_context=ctx)

    details = exc.value.details
    assert details.get("reason_code") == "denied"
    assert details.get("approval") == "user_deny", (
        "deny 侧 approval 与 reason_code 同走 ToolError.details"
    )


async def test_denied_tool_result_propagates_user_deny() -> None:
    """tool_executor 错误路径把 approval 从 ToolError.details lift 进 ToolResult。"""
    from agent.core.agent.tool_executor import StreamingToolExecutor
    from agent.core.types import ToolCall

    hooks = HookRegistry()

    async def gate(event, ctx):  # noqa: ANN001
        return {"block": True, "reason": "user denied", "approval": "user_deny"}

    hooks.on("tool_call", gate, priority=20)
    registry = _build_registry(hooks)
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-deny2"},
    )

    executor = StreamingToolExecutor(registry, hook_context=ctx)
    executor.add_tool(
        ToolCall(call_id="call-deny2", name="echo", arguments={"text": "hi"})
    )
    results = [r async for r in executor.get_remaining_results()]

    assert results[0].reason_code == "denied"
    assert results[0].approval == "user_deny"


# ---------------------------------------------------------------------------
# types: ToolResult 新增 approval 字段
# ---------------------------------------------------------------------------


def test_tool_result_has_approval_field_defaulting_none() -> None:
    from agent.core.types import ToolResult

    r = ToolResult(call_id="c", name="echo")
    assert r.approval is None
    r2 = ToolResult(call_id="c", name="echo", approval="user_allow")
    assert r2.approval == "user_allow"
