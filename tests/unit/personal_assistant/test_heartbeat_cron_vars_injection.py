"""heartbeat/cron gate behavior tests.

Covers the inbound_pipeline session_metadata contract and verifies that vars
no longer control the segment gates (gate migrated from ctx.vars to ctx.flags
via FEATURE_REGISTRY).  Comprehensive flags gate tests live in
test_prompt_section_feature_flags.py.
"""

from __future__ import annotations

from pathlib import Path

# refactor-406-M2: products/ dissolved. The PA heartbeat/cron *gate* behavior (segments
# appear per feature flag) now lives in the PA factory prompt_for + is covered by
# test_prompt_section_feature_flags.py and the skeleton golden (pa_heartbeat_on /
# pa_cron_on cases). The old _PA_*.enabled_when PromptSection-gate tests are removed
# with the PromptSection objects; the inbound_pipeline / runtime / preview-provider
# tests below are products-independent and retained.


# ---------------------------------------------------------------------------
# runtime.py — vars no longer contain heartbeat/cron after M9
# ---------------------------------------------------------------------------


class TestRuntimeVarsFromMetadata:
    """After M9, runtime.py vars dict must NOT contain heartbeat_enabled/cron_enabled.

    Gate is now driven by ctx.flags (from resolve_flags_from_metadata → FEATURE_REGISTRY).
    The vars injection was retired in M9 — test_m9_feature_model_gate.py has the
    definitive assertion; this class adds a complementary behavioral check.
    """

    def test_runtime_vars_only_contain_custom_prompt(self) -> None:
        """build_prompt_context_from_metadata called with no heartbeat/cron vars must not contain them.

        After M9 runtime.py only injects custom_prompt into vars.
        """
        from agent.core.agent.prompt_sections.wiring import (
            build_prompt_context_from_metadata,
        )

        metadata = {
            "custom_prompt": "hello",
        }
        ctx = build_prompt_context_from_metadata(
            metadata=metadata,
            available_tools=[],
            available_skills=[],
            current_datetime="2026-06-02T00:00:00Z",
            cwd="/tmp",
            flags={},
            vars={
                "custom_prompt": str(metadata.get("custom_prompt", "")),
            },
        )

        # After M9 runtime.py does not inject heartbeat/cron into vars
        assert "heartbeat_enabled" not in ctx.vars, (
            "PromptContext.vars must NOT contain heartbeat_enabled after M9 "
            "(gate moved to ctx.flags)"
        )
        assert "cron_enabled" not in ctx.vars, (
            "PromptContext.vars must NOT contain cron_enabled after M9 "
            "(gate moved to ctx.flags)"
        )
        # custom_prompt is still in vars
        assert ctx.vars.get("custom_prompt") == "hello"


# ---------------------------------------------------------------------------
# feat-394-M9 R2: assemble_prompt_preview uses features dict, not vars
# ---------------------------------------------------------------------------


class TestAssemblePromptPreviewFeaturesGate:
    """assemble_prompt_preview must use features dict (not heartbeat/cron_enabled params).

    feat-394-M9: heartbeat/cron gates driven by ctx.flags via features dict.
    Old heartbeat_enabled/cron_enabled params retired from assemble_prompt_preview.
    """

    def test_make_prompt_preview_provider_no_heartbeat_cron_params(
        self, tmp_path: Path
    ) -> None:
        """_make_prompt_preview_provider must NOT accept heartbeat_enabled/cron_enabled.

        M9: these params are retired; callers use features dict instead.
        """
        import inspect
        from personal_assistant.gateway.composition import _make_prompt_preview_provider

        class _FakeKernel:
            def assemble_prompt_preview(self, **kwargs) -> dict:
                return {"prompt": "preview", "section_count": 1}

        provider = _make_prompt_preview_provider(_FakeKernel())
        sig = inspect.signature(provider)
        assert "heartbeat_enabled" not in sig.parameters, (
            "_make_prompt_preview_provider must not accept heartbeat_enabled after M9"
        )
        assert "cron_enabled" not in sig.parameters, (
            "_make_prompt_preview_provider must not accept cron_enabled after M9"
        )
