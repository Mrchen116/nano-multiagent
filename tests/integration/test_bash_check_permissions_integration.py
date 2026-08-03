"""Verify bash permission policy is connected to registry hook dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.core.tools.registry import ToolRegistry
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _make_registry(tmp_path: Path) -> ToolRegistry:
    hooks = build_hook_registry(repo_root=tmp_path)
    hook_runner = HookRunner(registry=hooks)
    ctx = ToolContext.create(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ctx,
        hook_runner=hook_runner,
    )
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=None)
    registry.register(BashTool(wiring=wiring))
    return registry


@pytest.mark.parametrize("command", ("git status", "python3 --version"))
@pytest.mark.asyncio
async def test_safe_bash_commands_bypass_classifier_through_registry(
    tmp_path: Path,
    command: str,
) -> None:
    """Safe commands reach execution when no classifier is available."""
    registry = _make_registry(tmp_path)
    try:
        await registry.execute(
            "bash",
            {"command": command},
            hook_context=HookContext(
                session_id="safe-bash",
                repo_root=tmp_path,
                metadata={"tool_call_id": "safe-bash-call"},
            ),
        )
    except ToolError as error:
        assert error.details.get("blocked_by_hook") is not True


@pytest.mark.asyncio
async def test_python3_script_goes_to_classifier_and_blocks_fail_closed(
    tmp_path: Path,
) -> None:
    """Unlisted commands fail closed when no classifier is available."""
    registry = _make_registry(tmp_path)
    with pytest.raises(ToolError, match="tool blocked by hook"):
        await registry.execute(
            "bash",
            {"command": "python3 /tmp/run.py"},
            hook_context=HookContext(
                session_id="sess-r5-3",
                repo_root=tmp_path,
                metadata={"tool_call_id": "call-r5-3"},
            ),
        )
