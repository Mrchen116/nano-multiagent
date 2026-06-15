"""Tests for the PA cron prompt segments verbatim baseline (feat-394-M2 R8).

refactor-406-M2: products/ dissolved. The pa.cron / pa.cron_routing segment text now
lives in the PA production factory (personal_assistant.product._PA_CRON_TEXT /
_PA_CRON_ROUTING_TEXT). These verbatim tests are a refactor-406 risk-1 migration
invariant (byte-identical) and守的是真实生产段——同源于 the skeleton golden
(pa_cron_on / pa_both_on cases) which independently pins the assembled bytes.

The old PromptSection-gate tests (PA_SECTIONS membership, _PA_CRON.enabled_when,
LOCAL_CODING_PROFILE sections) are removed with the PromptSection objects: cron
segment presence per feature flag is now driven by prompt_for(if cron_enabled) and
covered by the skeleton golden + test_prompt_section_feature_flags.
"""

from __future__ import annotations

import inspect


class TestCronPromptSegmentVerbatim:
    """pa.cron / pa.cron_routing text must stay byte-identical (risk-1)."""

    def test_pa_cron_segment_renders_verbatim(self) -> None:
        """_PA_CRON_TEXT must be the exact byte-identical openclaw-derived baseline."""
        from personal_assistant.product import _PA_CRON_TEXT  # noqa: PLC2701

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
        assert _PA_CRON_TEXT == expected, (
            "pa.cron text drifted from verbatim baseline (risk-1)"
        )

    def test_pa_cron_routing_segment_renders_verbatim(self) -> None:
        """_PA_CRON_ROUTING_TEXT must be byte-identical to the baseline."""
        from personal_assistant.product import _PA_CRON_ROUTING_TEXT  # noqa: PLC2701

        expected = (
            "## Scheduling Routing\n"
            "You have both heartbeat and cron available. Use the right one:\n"
            "- **Heartbeat** (带上下文): for open-ended monitoring, reminders that need conversation\n"
            "  context, or tasks where you must remember what you discussed with the user.\n"
            '  Example: "Remind me about our discussion on the release" → heartbeat (HEARTBEAT.md).\n'
            "- **Cron** (无上下文): for deterministic scheduled tasks with a fixed instruction.\n"
            '  Example: "Every day at 9am summarize my GitHub notifications" → cron job.'
        )
        assert _PA_CRON_ROUTING_TEXT == expected, (
            "pa.cron_routing text drifted from verbatim baseline (risk-1)"
        )

    def test_pa_cron_segment_provenance_in_source(self) -> None:
        """The PA factory module must carry a Provenance comment for the cron segment.

        feat-394 decision 6: prompt segment text traced to its source.
        """
        import personal_assistant.product as pa_module

        source = inspect.getsource(pa_module)
        assert "_PA_CRON_TEXT" in source and "Provenance:" in source, (
            "personal_assistant.product must carry a 'Provenance:' comment for the "
            "cron segment (feat-394 decision 6)"
        )
