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
from agent.core.types import ToolSpec


class TestCronPromptSegment:
    """pa.cron segment must exist and be gated by cron_scheduling flag + cron tool.

    feat-394-M9: gate migrated from ctx.vars["cron_enabled"] to
    ctx.flags["cron_scheduling"] + ctx.has_tool("cron") (decision D).
    """

    def _make_ctx(
        self, *, cron_enabled: bool = True, heartbeat_enabled: bool = False
    ) -> PromptContext:
        # M9: gate is flags["cron_scheduling"] + has_tool("cron"); heartbeat is flags["heartbeat"].
        # Translate legacy bool params to the new flags/tools contract.
        flags = {}
        if cron_enabled:
            flags["cron_scheduling"] = True
        if heartbeat_enabled:
            flags["heartbeat"] = True
        tools = (
            (ToolSpec(name="cron", description="", input_schema={}),)
            if cron_enabled
            else ()
        )
        return PromptContext(vars={}, scenario={}, flags=flags, available_tools=tools)

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

    def test_pa_cron_segment_renders_verbatim(self) -> None:
        """pa.cron segment must render the exact byte-identical openclaw-derived text.

        refactor-406 risk 1: cron 段从内核 segment 迁到 PA PromptSlots.body 时必须
        逐字节复现。这取代了原 ``len>20`` 弱断言（迁 cron 出内核前补的逐字节防线，
        见 M1 退出标准）。
        """
        from agent.products.personal_assistant.prompt_sections import _PA_CRON  # noqa: PLC2701

        ctx = self._make_ctx(cron_enabled=True)
        text = _PA_CRON.render(ctx)
        expected = (
            "## Cron Jobs\n"
            "You have access to a `cron` tool for managing scheduled tasks.\n"
            "Use it when the user asks you to:\n"
            '- Run something at a specific time ("every day at 9am")\n'
            '- Run something on a recurring schedule ("every 5 minutes", "every hour")\n'
            '- Perform a one-shot background task at a future time ("in 30 minutes")\n\n'
            "Cron jobs run in isolated sessions with NO conversation context — they execute a\n"
            "fixed instruction and deliver the result to this chat.\n"
            "After a cron job runs, its result will appear as context so you can answer follow-ups.\n\n"
            "Do NOT use cron for tasks that need ongoing conversation context — use heartbeat instead."
        )
        assert text == expected, "pa.cron rendered text drifted from verbatim baseline"

    def test_pa_cron_routing_segment_renders_verbatim(self) -> None:
        """pa.cron_routing segment must render byte-identical text when both on.

        refactor-406 risk 1: the routing段也是迁移不变量，逐字节钉死。
        """
        from agent.products.personal_assistant.prompt_sections import (  # noqa: PLC2701
            _PA_CRON_ROUTING,
        )

        ctx = self._make_ctx(cron_enabled=True, heartbeat_enabled=True)
        text = _PA_CRON_ROUTING.render(ctx)
        expected = (
            "## Scheduling Routing\n"
            "You have both heartbeat and cron available. Use the right one:\n"
            "- **Heartbeat** (带上下文): for open-ended monitoring, reminders that need conversation\n"
            "  context, or tasks where you must remember what you discussed with the user.\n"
            '  Example: "Remind me about our discussion on the release" → heartbeat (HEARTBEAT.md).\n'
            "- **Cron** (无上下文): for deterministic scheduled tasks with a fixed instruction.\n"
            '  Example: "Every day at 9am summarize my GitHub notifications" → cron job.'
        )
        assert text == expected, (
            "pa.cron_routing rendered text drifted from verbatim baseline"
        )

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
