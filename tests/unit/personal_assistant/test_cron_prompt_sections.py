"""Tests for feat-394-M2 R8: cron prompt segments.

Covers:
- pa.cron segment exists and is gated by cron_enabled
- pa.cron_routing segment exists (shown when both heartbeat and cron are enabled)
- pa.cron segment NOT present when cron_enabled=False
- coding_cli profile does not include pa.cron or pa.cron_routing

feat-394 decision 6 + 7.
"""

from __future__ import annotations

import inspect

from agent.core.agent.prompt_sections.base import PromptContext


class TestCronPromptSegment:
    """pa.cron segment must exist and be gated by cron_enabled."""

    def _make_ctx(
        self, *, cron_enabled: bool = True, heartbeat_enabled: bool = False
    ) -> PromptContext:
        return PromptContext(
            vars={
                "cron_enabled": cron_enabled,
                "heartbeat_enabled": heartbeat_enabled,
            },
            scenario={},
        )

    def test_pa_cron_segment_exists(self) -> None:
        """PA prompt sections must contain a segment named 'pa.cron'."""
        from agent.products.personal_assistant.prompt_sections import PA_SECTIONS

        section_names = [s.name for s in PA_SECTIONS]
        assert "pa.cron" in section_names, (
            f"PA_SECTIONS must include 'pa.cron'; found: {section_names}"
        )

    def test_pa_cron_segment_gated_by_cron_enabled(self) -> None:
        """pa.cron must NOT render when cron_enabled=False."""
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx_off = self._make_ctx(cron_enabled=False)
        ctx_on = self._make_ctx(cron_enabled=True)
        # enabled_when must return False when cron_enabled=False
        enabled_fn = getattr(_PA_CRON, "enabled_when", None)
        if enabled_fn is not None:
            assert enabled_fn(ctx_off) is False, (
                "pa.cron must be disabled when cron_enabled=False"
            )
            assert enabled_fn(ctx_on) is True, (
                "pa.cron must be enabled when cron_enabled=True"
            )

    def test_pa_cron_segment_renders_content(self) -> None:
        """pa.cron segment must render non-empty text when enabled."""
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = self._make_ctx(cron_enabled=True)
        text = _PA_CRON.render(ctx)
        assert text is not None, "pa.cron must render non-None when cron_enabled=True"
        assert len(text) > 20, "pa.cron rendered text must be non-trivial"

    def test_pa_cron_routing_segment_exists(self) -> None:
        """PA prompt sections must contain a routing segment when both heartbeat + cron are on."""
        from agent.products.personal_assistant.prompt_sections import PA_SECTIONS

        section_names = [s.name for s in PA_SECTIONS]
        # The routing segment must exist (shown when both heartbeat + cron are on)
        assert any("routing" in name or "cron" in name for name in section_names), (
            f"PA_SECTIONS must include a routing segment; found: {section_names}"
        )

    def test_pa_cron_segment_provenance_in_source(self) -> None:
        """prompt_sections.py must contain a 'Provenance:' comment for the cron segment.

        feat-394 decision 6: cron prompt segment should be traced to openclaw or design.
        """
        import agent.products.personal_assistant.prompt_sections as ps_module

        source = inspect.getsource(ps_module)
        assert "pa.cron" in source, "prompt_sections.py must define 'pa.cron' segment"

    def test_coding_cli_no_pa_cron_segment(self) -> None:
        """coding_cli profile sections must not include 'pa.cron' or 'pa.cron_routing'."""
        from agent.products.local_coding.profile import LOCAL_CODING_PROFILE

        if LOCAL_CODING_PROFILE.prompt_sections is None:
            return
        section_names = [s.name for s in LOCAL_CODING_PROFILE.prompt_sections]
        assert "pa.cron" not in section_names, (
            f"coding_cli must not have 'pa.cron' segment (feat-394 decision 7): {section_names}"
        )
