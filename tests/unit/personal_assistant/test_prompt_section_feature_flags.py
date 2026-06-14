"""runtime/kernel no longer carry retired heartbeat/cron vars/params (feat-394-M9).

refactor-406-M2: products/ dissolved. The PromptSection-gate tests (which asserted
_PA_HEARTBEAT/_PA_CRON.enabled_when by ctx.flags) are removed with the PromptSection
objects — the heartbeat/cron segment gate behavior is now driven by the PA factory
prompt_for(if flag) and covered byte-identically by the skeleton golden
(pa_heartbeat_on / pa_cron_on / pa_both_on cases). The retained tests below check
runtime.py / Kernel.assemble_prompt_preview source-level invariants (products-independent).
"""

from __future__ import annotations


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
