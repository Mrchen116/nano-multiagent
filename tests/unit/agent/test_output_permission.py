"""Output publication evaluates registered tool permissions without execution."""

from dataclasses import replace

import pytest

from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMMessage
from agent.core.tools.registry import ToolRegistry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


@pytest.mark.parametrize("blocked", [False, True])
async def test_output_authorization_shares_interceptors_without_tool_observers(
    tmp_path, blocked
):
    observed = []
    checked = []
    executed = []

    class Tool:
        name = "send_message"
        description = "Send"
        input_schema = {"type": "object"}

        def run(self, args, context):
            executed.append(args)
            return {"sent": True}

    async def permission(event, context):
        checked.append((event, context))
        return {"block": blocked, "reason": "user denied" if blocked else None}

    async def observer(event, context):
        observed.append(event)

    hooks = HookRegistry()
    hooks.on("tool_call", permission, mode="intercept", priority=1)
    hooks.on("tool_call", observer)
    registry = ToolRegistry(
        context=ToolContext(
            repo_root=tmp_path,
            cwd=tmp_path,
            safety=ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig()),
        ),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(Tool())
    context = HookContext(
        session_id="session",
        metadata={"run_id": "run", "cwd": str(tmp_path)},
        message_history=(LLMMessage(role="user", content="Send this image"),),
    )
    outcome = await registry.evaluate_permission(
        "send_message",
        {"target": "chat", "text": "![x](/tmp/x.png)"},
        hook_context=context,
        action_id="operation-1",
        permission_only=True,
    )
    assert bool(outcome["block"]) is blocked
    assert len(checked) == 1
    event, actual = checked[0]
    assert event["call_id"] == "operation-1"
    assert actual.message_history == context.message_history
    assert actual.metadata["cwd"] == str(tmp_path)
    assert actual.metadata["tool_registry"] is registry
    assert not observed
    assert not executed
    if not blocked:
        await registry.execute(
            "send_message",
            {"text": "ordinary"},
            hook_context=replace(
                context, metadata={**context.metadata, "tool_call_id": "real_call"}
            ),
        )
        assert len(checked) == 2
        assert len(observed) == 1
        assert len(executed) == 1


@pytest.mark.parametrize("behavior", ["allow", "deny"])
async def test_output_uses_real_registered_tool_permission_gate(tmp_path, behavior):
    from agent.platform.config.auto_mode import AutoModeConfig
    from agent.platform.hooks.builtins.auto_mode_gate import setup
    from agent.platform.permissions.broker import PermissionDecision

    checks = []

    class Tool:
        name = "send_message"
        description = "Send"
        input_schema = {"type": "object"}

        def check_permissions(self, args, context):
            checks.append((args, context))
            return PermissionDecision(behavior=behavior, reason="tool policy")

        def run(self, args, context):
            raise AssertionError("authorization must not execute tool")

    hooks = HookRegistry()
    setup(hooks)
    registry = ToolRegistry(
        context=ToolContext(
            repo_root=tmp_path,
            cwd=tmp_path,
            safety=ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig()),
        ),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(Tool())
    context = HookContext(
        session_id="session",
        metadata={"_auto_mode_config_loader": lambda: AutoModeConfig(enabled=True)},
    )
    outcome = await registry.evaluate_permission(
        "send_message",
        {"target": "chat", "text": "image"},
        hook_context=context,
        action_id="operation-2",
        permission_only=True,
    )
    assert (not outcome["block"]) is (behavior == "allow")
    assert len(checks) == 1
