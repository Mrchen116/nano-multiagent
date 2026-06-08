"""heartbeat/cron prompt segments gated by ctx.flags (FEATURE_REGISTRY).

The gate mechanism uses ctx.flags["heartbeat"] / ctx.flags["cron_scheduling"],
matching the memory_curation / skill_creation pattern.  The legacy
ctx.vars gate is retired.
"""

from __future__ import annotations

from agent.core.agent.prompt_sections.base import PromptContext
from agent.core.types import ToolSpec


def _ctx_with_flags(**flags: bool) -> PromptContext:
    """Build a PromptContext with given feature flags and no vars."""
    return PromptContext(vars={}, scenario={}, flags=dict(flags))


def _ctx_with_flags_and_tools(flags: dict, tools: list[str]) -> PromptContext:
    """Build a PromptContext with given flags and available ToolSpec stubs."""
    # has_tool() checks getattr(t, "name", None), so we must pass ToolSpec objects.
    tool_specs = tuple(ToolSpec(name=t, description="", input_schema={}) for t in tools)
    return PromptContext(vars={}, scenario={}, flags=flags, available_tools=tool_specs)


# ---------------------------------------------------------------------------
# _PA_HEARTBEAT: gated by ctx.flags.get("heartbeat", False)
# ---------------------------------------------------------------------------


class TestHeartbeatFlagsGate:
    """_PA_HEARTBEAT must be controlled by ctx.flags["heartbeat"] not ctx.vars."""

    def test_heartbeat_disabled_by_default_flags(self) -> None:
        """_PA_HEARTBEAT must be disabled when ctx.flags has no "heartbeat" key.

        After M9: heartbeat is opt-in (default_on=False), so absent flag = off.
        Before M9: absent ctx.vars["heartbeat_enabled"] defaults to True (backward compat).
        """
        from agent.products.personal_assistant.prompt_sections import _PA_HEARTBEAT  # noqa: PLC2701

        ctx = PromptContext(vars={}, scenario={})
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is False, (
            "_PA_HEARTBEAT must be disabled when ctx.flags has no 'heartbeat' key "
            "(M9: heartbeat is opt-in via FEATURE_REGISTRY default_on=False)"
        )

    def test_heartbeat_disabled_when_flag_false(self) -> None:
        """_PA_HEARTBEAT must be disabled when ctx.flags["heartbeat"] is False."""
        from agent.products.personal_assistant.prompt_sections import _PA_HEARTBEAT  # noqa: PLC2701

        ctx = _ctx_with_flags(heartbeat=False)
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is False, (
            "_PA_HEARTBEAT must be disabled when ctx.flags['heartbeat']=False"
        )

    def test_heartbeat_enabled_when_flag_true(self) -> None:
        """_PA_HEARTBEAT must be enabled when ctx.flags["heartbeat"] is True."""
        from agent.products.personal_assistant.prompt_sections import _PA_HEARTBEAT  # noqa: PLC2701

        ctx = _ctx_with_flags(heartbeat=True)
        assert _PA_HEARTBEAT.enabled_when is not None
        assert _PA_HEARTBEAT.enabled_when(ctx) is True, (
            "_PA_HEARTBEAT must be enabled when ctx.flags['heartbeat']=True"
        )

    def test_heartbeat_gate_ignores_vars(self) -> None:
        """_PA_HEARTBEAT must NOT be enabled by ctx.vars['heartbeat_enabled']='True'.

        After M9: ctx.vars gate is retired. Only ctx.flags counts.
        """
        from agent.products.personal_assistant.prompt_sections import _PA_HEARTBEAT  # noqa: PLC2701

        # Old-style vars gate (pre-M9): should no longer enable the segment
        ctx = PromptContext(
            vars={"heartbeat_enabled": "True"},
            scenario={},
            flags={"heartbeat": False},
        )
        assert _PA_HEARTBEAT.enabled_when is not None
        # flags["heartbeat"]=False must win — vars are retired
        assert _PA_HEARTBEAT.enabled_when(ctx) is False, (
            "_PA_HEARTBEAT must NOT be enabled by vars['heartbeat_enabled'] after M9; "
            "only ctx.flags['heartbeat'] counts"
        )


# ---------------------------------------------------------------------------
# _PA_CRON: gated by ctx.flags.get("cron_scheduling", False) and ctx.has_tool("cron")
# ---------------------------------------------------------------------------


class TestCronFlagsGate:
    """_PA_CRON must be controlled by ctx.flags["cron_scheduling"] AND ctx.has_tool("cron")."""

    def test_cron_disabled_by_default_flags(self) -> None:
        """_PA_CRON must be disabled when ctx.flags has no "cron_scheduling" key."""
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = PromptContext(vars={}, scenario={})
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False, (
            "_PA_CRON must be disabled when ctx.flags has no 'cron_scheduling' key"
        )

    def test_cron_disabled_when_flag_false(self) -> None:
        """_PA_CRON must be disabled when ctx.flags["cron_scheduling"] is False."""
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = _ctx_with_flags_and_tools({"cron_scheduling": False}, ["cron"])
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False

    def test_cron_disabled_when_flag_true_but_no_cron_tool(self) -> None:
        """_PA_CRON must be disabled when cron_scheduling=True but cron tool absent.

        This mirrors _memory_guidance_enabled (requires both flag AND tool).
        """
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = _ctx_with_flags_and_tools({"cron_scheduling": True}, [])
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False, (
            "_PA_CRON must require cron tool to be present (like memory_curation requires memory)"
        )

    def test_cron_enabled_when_flag_true_and_cron_tool_present(self) -> None:
        """_PA_CRON must be enabled when cron_scheduling=True AND cron tool present."""
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = _ctx_with_flags_and_tools({"cron_scheduling": True}, ["cron"])
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is True, (
            "_PA_CRON must be enabled when cron_scheduling=True and cron tool is present"
        )

    def test_cron_gate_ignores_vars(self) -> None:
        """_PA_CRON must NOT be enabled by ctx.vars['cron_enabled']='True' after M9."""
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = PromptContext(
            vars={"cron_enabled": "True"},
            scenario={},
            flags={"cron_scheduling": False},
            available_tools=["cron"],
        )
        assert _PA_CRON.enabled_when is not None
        assert _PA_CRON.enabled_when(ctx) is False, (
            "_PA_CRON must NOT be enabled by vars['cron_enabled'] after M9; "
            "only ctx.flags['cron_scheduling'] + has_tool('cron') counts"
        )


# ---------------------------------------------------------------------------
# _PA_CRON_ROUTING: gated by both flags
# ---------------------------------------------------------------------------


class TestCronRoutingFlagsGate:
    """_PA_CRON_ROUTING must require both heartbeat=True and cron_scheduling=True+tool."""

    def test_routing_disabled_when_neither_flag_set(self) -> None:
        from agent.products.personal_assistant.prompt_sections import _PA_CRON_ROUTING  # noqa: PLC2701

        ctx = PromptContext(vars={}, scenario={})
        assert _PA_CRON_ROUTING.enabled_when is not None
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False

    def test_routing_disabled_when_only_heartbeat(self) -> None:
        from agent.products.personal_assistant.prompt_sections import _PA_CRON_ROUTING  # noqa: PLC2701

        ctx = _ctx_with_flags_and_tools(
            {"heartbeat": True, "cron_scheduling": False}, ["cron"]
        )
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False

    def test_routing_disabled_when_only_cron(self) -> None:
        from agent.products.personal_assistant.prompt_sections import _PA_CRON_ROUTING  # noqa: PLC2701

        ctx = _ctx_with_flags_and_tools(
            {"heartbeat": False, "cron_scheduling": True}, ["cron"]
        )
        assert _PA_CRON_ROUTING.enabled_when(ctx) is False

    def test_routing_enabled_when_both_flags_and_cron_tool(self) -> None:
        from agent.products.personal_assistant.prompt_sections import _PA_CRON_ROUTING  # noqa: PLC2701

        ctx = _ctx_with_flags_and_tools(
            {"heartbeat": True, "cron_scheduling": True}, ["cron"]
        )
        assert _PA_CRON_ROUTING.enabled_when(ctx) is True


# ---------------------------------------------------------------------------
# runtime.py no longer injects heartbeat_enabled/cron_enabled into vars
# ---------------------------------------------------------------------------


class TestRuntimeNoLongerInjectsVars:
    """After M9, runtime.py must NOT inject heartbeat_enabled/cron_enabled into ctx.vars.

    Gate is now driven by ctx.flags (from resolve_flags_from_metadata → FEATURE_REGISTRY).
    Injecting into vars is dead code that should be removed.
    """

    def test_runtime_vars_do_not_contain_heartbeat_enabled(self) -> None:
        """runtime.py vars dict must NOT include heartbeat_enabled after M9."""
        import ast
        import inspect
        import importlib

        runtime_mod = importlib.import_module("agent.core.agent.runtime")
        source = inspect.getsource(runtime_mod)

        # We check that the string injection is gone
        assert '"heartbeat_enabled": str(' not in source, (
            "runtime.py must not inject heartbeat_enabled into vars after M9 "
            "(gate moved to ctx.flags via FEATURE_REGISTRY)"
        )

    def test_runtime_vars_do_not_contain_cron_enabled(self) -> None:
        """runtime.py vars dict must NOT include cron_enabled after M9."""
        import inspect
        import importlib

        runtime_mod = importlib.import_module("agent.core.agent.runtime")
        source = inspect.getsource(runtime_mod)

        assert '"cron_enabled": str(' not in source, (
            "runtime.py must not inject cron_enabled into vars after M9 "
            "(gate moved to ctx.flags via FEATURE_REGISTRY)"
        )


# ---------------------------------------------------------------------------
# kernel.py assemble_prompt_preview: no longer needs heartbeat/cron params
# ---------------------------------------------------------------------------


class TestKernelPreviewNoHeartbeatCronParams:
    """assemble_prompt_preview must NOT have heartbeat_enabled/cron_enabled params after M9.

    After M9: features dict drives flags via resolve_flags_from_metadata;
    heartbeat_enabled/cron_enabled params are dead code.
    """

    def test_assemble_prompt_preview_no_heartbeat_param(self) -> None:
        """assemble_prompt_preview signature must not have heartbeat_enabled param."""
        import inspect
        from agent.sdk.kernel import Kernel

        sig = inspect.signature(Kernel.assemble_prompt_preview)
        assert "heartbeat_enabled" not in sig.parameters, (
            "Kernel.assemble_prompt_preview must not have heartbeat_enabled param after M9"
        )

    def test_assemble_prompt_preview_no_cron_param(self) -> None:
        """assemble_prompt_preview signature must not have cron_enabled param."""
        import inspect
        from agent.sdk.kernel import Kernel

        sig = inspect.signature(Kernel.assemble_prompt_preview)
        assert "cron_enabled" not in sig.parameters, (
            "Kernel.assemble_prompt_preview must not have cron_enabled param after M9"
        )
