from pathlib import Path

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.hooks.context import HookContext, HookModelCall, HookModelResult
from nano_multiagent.hooks.loader import build_hook_registry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.bash import BashTool
from nano_multiagent.tools.registry import ToolRegistry


def test_builtin_bash_risk_hook_allows_unlisted_command_after_safe_review(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def model_caller(call: HookModelCall) -> HookModelResult:
        captured["session_id"] = call.session_id
        captured["user_prompt"] = call.user_prompt
        return HookModelResult(
            model="mock-risk",
            content='{"risk":"safe","reason":"read-only query"}',
            raw={},
        )

    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(BashTool())

    result = registry.execute(
        "bash",
        {"command": "uname -s"},
        hook_context=HookContext(
            session_id="sess-risk-1",
            repo_root=tmp_path,
            metadata={"tool_call_id": "call-risk-1"},
            model_caller=model_caller,
        ),
    )

    assert result["exitCode"] == 0
    assert "Darwin" in str(result["content"])
    assert captured["session_id"] == "sess-risk-1"
    assert str(captured["user_prompt"]).endswith("command: uname -s")


def test_builtin_bash_risk_hook_blocks_unlisted_unsafe_command(tmp_path: Path) -> None:
    def model_caller(call: HookModelCall) -> HookModelResult:
        del call
        return HookModelResult(
            model="mock-risk",
            content='{"risk":"unsafe","reason":"modifies system state"}',
            raw={},
        )

    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(BashTool())

    with pytest.raises(ToolError, match="tool blocked by hook") as exc_info:
        registry.execute(
            "bash",
            {"command": "uname -a"},
            hook_context=HookContext(
                session_id="sess-risk-2",
                repo_root=tmp_path,
                metadata={"tool_call_id": "call-risk-2"},
                model_caller=model_caller,
            ),
        )

    reason = str(exc_info.value.details.get("reason", ""))
    assert "modifies system state" in reason


def test_builtin_bash_risk_hook_blocks_when_model_caller_is_missing(tmp_path: Path) -> None:
    hooks = build_hook_registry(repo_root=tmp_path)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(BashTool())

    with pytest.raises(ToolError, match="tool blocked by hook") as exc_info:
        registry.execute(
            "bash",
            {"command": "uname -a"},
            hook_context=HookContext(
                session_id="sess-risk-3",
                repo_root=tmp_path,
                metadata={"tool_call_id": "call-risk-3"},
            ),
        )

    assert "model caller is unavailable" in str(exc_info.value.details.get("reason", ""))
