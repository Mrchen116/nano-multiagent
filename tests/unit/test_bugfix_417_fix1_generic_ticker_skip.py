"""bugfix-417-fix1 (D): the executor's generic liveness ticker must SKIP tools that
emit their own execution events (bash), so a bash run does not get 2x run_heartbeat
writes per interval (its own phase:running + the generic phase:executing). Non
self-emitting tools still get the generic ticker.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, Mapping

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import Tool, ToolContext
from agent.core.tools.registry import ToolRegistry

pytestmark = pytest.mark.asyncio


class _BlockingTool(Tool):
    """Blocks in run() until released, so the test can observe whether the generic
    executing-phase ticker fired while it was in flight."""

    input_schema = {"type": "object", "properties": {}, "additionalProperties": True}

    def __init__(
        self, name: str, release: threading.Event, *, self_emits: bool
    ) -> None:
        self.name = name
        self.description = "block until released"
        self._release = release
        if self_emits:
            # Mirror BashTool's marker so the executor skips the generic ticker.
            self.emits_own_execution_events = True

    def run(self, args: Mapping[str, Any], context: ToolContext) -> Mapping[str, Any]:
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


async def _run_and_collect_executing(
    monkeypatch: pytest.MonkeyPatch, tool_name: str, *, self_emits: bool
) -> list[Mapping[str, Any]]:
    # Tiny generic interval so a tick would fire well within the observation window.
    monkeypatch.setattr(
        "agent.core.tools.registry._GENERIC_EXECUTION_HEARTBEAT_INTERVAL", 0.05
    )
    hooks = HookRegistry()
    release = threading.Event()
    seen: list[Mapping[str, Any]] = []

    async def observe_update(event, ctx):  # noqa: ANN001
        seen.append(dict(event))

    hooks.on("tool_execution_update", observe_update, priority=1000)
    registry = _build_registry(
        hooks, _BlockingTool(tool_name, release, self_emits=self_emits)
    )
    ctx = HookContext(
        session_id="s-1",
        repo_root=registry.context.repo_root,
        metadata={"tool_call_id": "call-1", "run_id": "run-1"},
    )

    exec_task = asyncio.create_task(registry.execute(tool_name, {}, hook_context=ctx))
    # Let several generic intervals elapse while the tool is blocked in run().
    await asyncio.sleep(0.25)
    release.set()
    await asyncio.wait_for(exec_task, timeout=2.0)
    return [u for u in seen if u.get("phase") == "executing"]


async def test_self_emitting_tool_skips_generic_executing_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tool with emits_own_execution_events=True must NOT receive generic
    phase:executing heartbeats (no double-fire)."""
    executing = await _run_and_collect_executing(
        monkeypatch, "self_emit_tool", self_emits=True
    )
    assert executing == [], (
        f"self-emitting tool got generic phase:executing ticks (double-fire): {executing}"
    )


async def test_non_self_emitting_tool_gets_generic_executing_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal tool (no self-emit) still gets the generic phase:executing ticker —
    the M6 coverage must not regress."""
    executing = await _run_and_collect_executing(
        monkeypatch, "plain_tool", self_emits=False
    )
    assert executing, "non-self-emitting tool lost its generic phase:executing ticker"
    assert executing[0].get("run_id") == "run-1"
