"""Output publication evaluates registered tool permissions without execution."""

from dataclasses import replace

import pytest

from agent.core.agent.output import BoundOutputControl
from agent.core.agent.run_control import RunController
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMMessage
from agent.core.tools.registry import ToolRegistry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig
from agent.sdk.output import _OutputControlAdapter


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
    control = _OutputControlAdapter(
        BoundOutputControl(RunController(), 0, registry, context)
    )
    outcome = await control.authorize_tool(
        "send_message", {"target": "chat", "text": "![x](/tmp/x.png)"}
    )
    assert outcome.allowed is not blocked
    assert len(checked) == 1
    event, actual = checked[0]
    assert event["call_id"].startswith("output_permission_")
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


def test_output_commit_rejects_cancelled_or_stale_run():
    controller = RunController(revalidate_output=True)
    control = BoundOutputControl(controller, 0, None, HookContext(session_id="session"))
    published = []
    controller.accepted_revision = 1
    assert control.try_commit(lambda: published.append(True)) == "stale"
    controller.abort()
    assert control.try_commit(lambda: published.append(True)) == "inactive"
    assert not published


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
    control = _OutputControlAdapter(
        BoundOutputControl(RunController(), 0, registry, context)
    )
    outcome = await control.authorize_tool(
        "send_message", {"target": "chat", "text": "image"}
    )
    assert outcome.allowed is (behavior == "allow")
    assert len(checks) == 1
