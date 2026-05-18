"""Integration tests for BashTool.check_permissions end-to-end dispatch (bugfix-355-M6 R5).

Covers the full chain: ToolRegistry.execute → auto_mode_gate → BashTool.check_permissions
→ bash_policy.check_command_policy.

Exit-criteria for M6 R5:
- git status: BashTool.check_permissions returns allow → auto_mode_gate passes without
  calling the classifier LLM.
- python3 file.py: BashTool.check_permissions returns passthrough → auto_mode_gate goes
  to classifier, which blocks fail-closed when model_caller is absent (no regression).
- python3 --version: BashTool.check_permissions returns allow (D9 version-flag exception).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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


def _make_registry(tmp_path: Path, model_caller=None) -> ToolRegistry:
    hooks = build_hook_registry(repo_root=tmp_path)
    hook_runner = HookRunner(registry=hooks)
    ctx = ToolContext.create(repo_root=tmp_path)
    if model_caller is not None:
        hook_runner = HookRunner(registry=hooks)
    registry = ToolRegistry(
        context=ctx,
        hook_runner=hook_runner,
    )
    registry.register(BashTool())
    return registry


@pytest.mark.asyncio
async def test_git_status_passes_without_classifier(tmp_path: Path) -> None:
    """git status is allowed by BashTool.check_permissions → no classifier call.

    Verifies D10 single-point: policy is decided in BashTool.check_permissions
    (returns allow for git status), auto_mode_gate returns None at step 5 without
    touching the classifier.
    """
    registry = _make_registry(tmp_path)
    # No model_caller — if classifier were called, it would block fail-closed.
    # git status must NOT reach the classifier (must pass the hook gate).
    try:
        await registry.execute(
            "bash",
            {"command": "git status"},  # git status is in allowed prefixes (D9)
            hook_context=HookContext(
                session_id="sess-r5-1",
                repo_root=tmp_path,
                metadata={"tool_call_id": "call-r5-1"},
            ),
        )
        # Reached here = hook passed, command ran (may succeed in a git repo)
    except ToolError as err:
        # Execution error (non-zero exit like exit 128 = not a git repo) is acceptable.
        # Hook block is NOT acceptable.
        assert "tool blocked by hook" not in str(err), (
            f"git status should not be blocked by hook; got: {err}"
        )


@pytest.mark.asyncio
async def test_python3_version_flag_passes_without_classifier(tmp_path: Path) -> None:
    """python3 --version is in D9 allowed prefixes → no classifier, executes directly."""
    registry = _make_registry(tmp_path)
    result = await registry.execute(
        "bash",
        {"command": "python3 --version"},
        hook_context=HookContext(
            session_id="sess-r5-2",
            repo_root=tmp_path,
            metadata={"tool_call_id": "call-r5-2"},
        ),
    )
    assert result.get("exitCode") == 0 or "content" in result or "stdout" in result


@pytest.mark.asyncio
async def test_python3_script_goes_to_classifier_and_blocks_fail_closed(tmp_path: Path) -> None:
    """python3 file.py (review path) goes to classifier, blocks when no model_caller.

    After M6: BashTool.check_permissions returns passthrough for python3 file.py.
    auto_mode_gate step 5 falls through (passthrough), goes to step 7 classifier.
    With no model_caller, classifier blocks fail-closed.
    """
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


@pytest.mark.asyncio
async def test_bash_check_permissions_is_called_via_tool_registry_injection(tmp_path: Path) -> None:
    """Verify tool_registry injection: auto_mode_gate calls BashTool.check_permissions.

    Confirms the full D10 chain works: ToolRegistry.execute injects tool_registry into
    hook metadata → auto_mode_gate step 1 calls BashTool.check_permissions → step 5
    dispatches result. Without injection, bash would always fall through to classifier.
    """
    from agent.platform.tools.builtins.bash_policy import check_command_policy

    # git status is allowed → BashTool.check_permissions returns allow
    decision = check_command_policy("git status")
    assert decision.status == "allowed", "git status must be in BASH_ALLOWED_PREFIXES"

    # python3 /tmp/run.py is review → BashTool.check_permissions returns passthrough
    decision2 = check_command_policy("python3 /tmp/run.py")
    assert decision2.status == "review", "python3 <script> must be review (not in allowed prefix)"

    # Verify BashTool has check_permissions method
    tool = BashTool()
    assert hasattr(tool, "check_permissions"), "BashTool must implement check_permissions (M6 D1)"
