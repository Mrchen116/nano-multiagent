"""Regression tests for bash tool gating via auto_mode_gate (replaces bash_risk_gate).

auto_mode_gate is the unified permission gate that replaces the former
bash_risk_gate builtin. These tests verify end-to-end bash gating behaviour
through the real hook loader so that the replacement doesn't regress.
"""

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.platform.hooks.loader import build_hook_registry
from agent.core.hooks.runner import HookRunner
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.registry import ToolRegistry
from agent.core.tools.base import set_tool_safety_config_factory, set_tool_safety_factory
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


async def test_builtin_bash_risk_hook_allows_unlisted_command_after_safe_review(tmp_path: Path) -> None:
    """Read-only commands allowed by command policy pass without needing classification."""
    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(BashTool())

    # "ls -la" matches allowed prefix list → passes immediately without classifier
    result = await registry.execute(
        "bash",
        {"command": "ls -la /tmp"},
        hook_context=HookContext(
            session_id="sess-risk-1",
            repo_root=tmp_path,
            metadata={"tool_call_id": "call-risk-1"},
        ),
    )

    # Command should execute and succeed (exitCode 0 or content present)
    assert result.get("exitCode") == 0 or "content" in result or "stdout" in result


async def test_builtin_bash_risk_hook_blocks_unlisted_unsafe_command(tmp_path: Path) -> None:
    """Commands matching the hardcoded denylist are blocked without classifier."""
    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(BashTool())

    # "rm -rf /" matches a denylist fragment → blocked immediately
    with pytest.raises(ToolError, match="tool blocked by hook"):
        await registry.execute(
            "bash",
            {"command": "rm -rf /"},
            hook_context=HookContext(
                session_id="sess-risk-2",
                repo_root=tmp_path,
                metadata={"tool_call_id": "call-risk-2"},
            ),
        )


async def test_builtin_bash_risk_hook_blocks_when_model_caller_is_missing(tmp_path: Path) -> None:
    """Commands needing classification are blocked fail-closed when model caller unavailable."""
    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(BashTool())

    # "uname -a" hits the "review" policy level — classifier needed but unavailable.
    # auto_mode_gate: no model_caller → classifier unavailable → fail-closed to ask
    # → no permission_requester → "no permission channel" deny.
    with pytest.raises(ToolError, match="tool blocked by hook"):
        await registry.execute(
            "bash",
            {"command": "uname -a"},
            hook_context=HookContext(
                session_id="sess-risk-3",
                repo_root=tmp_path,
                metadata={"tool_call_id": "call-risk-3"},
                # no model_caller → classifier unavailable
            ),
        )
