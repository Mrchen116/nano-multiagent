"""bugfix-417-M3 R1: 工具执行心跳必须实时 dispatch,不再缓冲到 run 结束才 flush.

事故链 B 层根因之一: tools/registry 的 `_emit_execution_update` 把工具运行期的
`phase:running` 心跳 append 到 `_pending_updates`,跑完才循环 flush。一个静默长命令
(如 `sleep 200`) 整段运行期内 observe 链一个事件都收不到,Gateway/IM watchdog 看到
"输出静默" 就误杀。修复后心跳经 `run_coroutine_threadsafe` 实时桥回 execute 所在 loop,
在工具结束前就 dispatch `tool_execution_update`,成为 watchdog 的 liveness 源。

观察点: 用一个在 `tool.run()` 同步体内 (经 asyncio.to_thread 工作线程) 周期回调
`execution_event_callback` 的慢工具;断言工具尚未返回时 observe handler 已收到 ≥1 个
`tool_execution_update` 事件。
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import Tool, ToolContext
from agent.core.tools.registry import ToolRegistry

pytestmark = pytest.mark.asyncio


class _HeartbeatTool(Tool):
    """A tool whose synchronous run() emits two phase:running heartbeats then a final
    one, gating its own completion on an Event so the test can observe mid-run dispatch.
    """

    name = "slow_cmd"
    description = "emit heartbeats then block until released"
    input_schema = {"type": "object", "properties": {}, "additionalProperties": True}

    def __init__(self, release: threading.Event) -> None:
        self._release = release

    def run(self, args: Mapping[str, Any], context: ToolContext) -> Mapping[str, Any]:
        cb = context.execution_event_callback
        assert cb is not None, "execution_event_callback must be injected"
        # Emit two heartbeats while the tool is still running.
        cb({"phase": "running", "status": "running", "elapsed_ms": 10})
        cb({"phase": "running", "status": "running", "elapsed_ms": 20})
        # Block until the test releases us, so it can assert the heartbeats were
        # dispatched *before* the tool returns.
        self._release.wait(timeout=2.0)
        return {"done": True}


def _build_registry(hooks: HookRegistry, tool: Tool) -> ToolRegistry:
    from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

    repo_root = Path("/tmp")
    safety = ToolSafety(repo_root=repo_root, config=ToolSafetyConfig())
    context = ToolContext(repo_root=repo_root, cwd=repo_root, safety=safety)
    runner = HookRunner(registry=hooks)
    registry = ToolRegistry(context=context, hook_runner=runner)
    registry.register(tool)
    return registry


async def test_tool_execution_update_dispatched_before_tool_returns() -> None:
    """心跳在工具 run() 仍阻塞时就经 observe 链 dispatch(实时),而非跑完才 flush."""
    hooks = HookRegistry()
    release = threading.Event()
    updates_seen = asyncio.Event()
    seen: list[Mapping[str, Any]] = []

    async def observe_update(event, ctx):  # noqa: ANN001
        seen.append(dict(event))
        updates_seen.set()

    hooks.on("tool_execution_update", observe_update, priority=1000)

    registry = _build_registry(hooks, _HeartbeatTool(release))
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-hb", "run_id": "run-hb"},
    )

    exec_task = asyncio.create_task(registry.execute("slow_cmd", {}, hook_context=ctx))

    # The tool is now blocked in run() (release not set). If heartbeats are dispatched
    # in real time we must observe at least one tool_execution_update WITHOUT releasing
    # the tool. If they were buffered (old behaviour), this wait times out.
    await asyncio.wait_for(updates_seen.wait(), timeout=1.5)
    assert not exec_task.done(), "tool must still be running when heartbeat observed"
    running_updates = [u for u in seen if u.get("phase") == "running"]
    assert running_updates, "expected at least one phase:running heartbeat mid-run"
    assert running_updates[0].get("run_id") == "run-hb"

    # Release the tool and let execute finish cleanly.
    release.set()
    result = await asyncio.wait_for(exec_task, timeout=2.0)
    assert result == {"done": True}
