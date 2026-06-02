"""Tests for feat-394-M1 R3: HEARTBEAT_OK silence token + openclaw prompt verbatim parity.

Covers two exit criteria from M1:
1. HEARTBEAT_OK must be recognised as a silence token (same as NO_REPLY in heartbeat context).
2. _PA_HEARTBEAT prompt segment text must be verbatim identical to openclaw buildHeartbeatSection.

These tests are red until R3 implementation lands.
"""
from __future__ import annotations

import pytest

from agent.core.agent.prompt_sections.base import PromptContext
from agent.products.personal_assistant.prompt_sections import _PA_HEARTBEAT  # noqa: PLC2701


# ---------------------------------------------------------------------------
# HEARTBEAT_OK silence token
# ---------------------------------------------------------------------------

class TestHeartbeatOkSilenceToken:
    """HEARTBEAT_OK must be recognised as a silence token in the heartbeat delivery path.

    Provenance: openclaw/src/auto-reply/heartbeat.ts — model replies "HEARTBEAT_OK" when
    nothing needs attention; the system strips it before any IM delivery.
    feat-394 decision 3: HEARTBEAT_OK replaces NO_REPLY as the heartbeat silence token.
    """

    def test_heartbeat_ok_detected_by_silence_check(self) -> None:
        """_is_no_reply_token must return True for 'HEARTBEAT_OK'.

        This is the gating check used in _build_kernel_event_observer for heartbeat runs.
        """
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline

        assert InboundPipeline._is_no_reply_token("HEARTBEAT_OK") is True  # noqa: SLF001

    def test_heartbeat_ok_with_whitespace_still_silent(self) -> None:
        """Trailing/leading whitespace around HEARTBEAT_OK must still be recognized."""
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline

        assert InboundPipeline._is_no_reply_token("  HEARTBEAT_OK  ") is True  # noqa: SLF001

    def test_no_reply_still_detected(self) -> None:
        """NO_REPLY must still be recognised as a silence token (regression guard)."""
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline

        assert InboundPipeline._is_no_reply_token("NO_REPLY") is True  # noqa: SLF001

    def test_non_silence_content_not_flagged(self) -> None:
        """Ordinary assistant content must NOT be flagged as a silence token."""
        from personal_assistant.gateway.inbound_pipeline import InboundPipeline

        assert InboundPipeline._is_no_reply_token("Here is your daily update.") is False  # noqa: SLF001
        assert InboundPipeline._is_no_reply_token("") is False  # noqa: SLF001


# ---------------------------------------------------------------------------
# Prompt segment verbatim parity with openclaw
# ---------------------------------------------------------------------------

class TestHeartbeatPromptOpenclawParity:
    """_PA_HEARTBEAT segment text must be verbatim identical to openclaw buildHeartbeatSection.

    Provenance:
      openclaw/src/agents/system-prompt.ts:124-138 buildHeartbeatSection(...)
      Text extracted from the non-minimal, heartbeat-prompt-present branch.

    feat-394 decision 6: heartbeat system segment copied verbatim from openclaw;
    code comment must include 'Provenance: openclaw/src/agents/system-prompt.ts:124'.
    """

    # Verbatim text from openclaw/src/agents/system-prompt.ts:124-138 buildHeartbeatSection
    # (non-minimal branch, heartbeatPrompt is set).
    _EXPECTED_LINES = [
        "## Heartbeats",
        "If the current user message is a heartbeat poll and nothing needs attention, reply exactly:",
        "HEARTBEAT_OK",
        'If something needs attention, do NOT include "HEARTBEAT_OK"; reply with the alert text instead.',
    ]

    def _make_ctx(self) -> PromptContext:
        return PromptContext(vars={}, scenario={})

    def test_heartbeat_segment_contains_heartbeat_ok_token(self) -> None:
        """The segment text must contain the exact HEARTBEAT_OK token string."""
        ctx = self._make_ctx()
        text = _PA_HEARTBEAT.render(ctx)
        assert text is not None, "_PA_HEARTBEAT must render (not return None)"
        assert "HEARTBEAT_OK" in text

    def test_heartbeat_segment_verbatim_openclaw_lines(self) -> None:
        """Each line from openclaw buildHeartbeatSection must appear verbatim in the segment.

        Provenance: openclaw/src/agents/system-prompt.ts:124-138
        """
        ctx = self._make_ctx()
        text = _PA_HEARTBEAT.render(ctx) or ""
        for line in self._EXPECTED_LINES:
            assert line in text, (
                f"Expected openclaw-verbatim line not found in _PA_HEARTBEAT segment:\n"
                f"  Missing: {line!r}\n"
                f"  Actual segment:\n{text}"
            )

    def test_heartbeat_segment_provenance_comment_in_source(self) -> None:
        """The prompt_sections.py file must contain a Provenance comment pointing to openclaw.

        feat-394 decision 6: code comment convention requires 'Provenance:' annotation
        with openclaw source file and line number.
        """
        import inspect
        import agent.products.personal_assistant.prompt_sections as ps_module

        source = inspect.getsource(ps_module)
        # The comment must reference openclaw source path (system-prompt.ts)
        assert "openclaw" in source and "system-prompt.ts" in source, (
            "prompt_sections.py must contain a 'Provenance:' comment referencing "
            "openclaw/src/agents/system-prompt.ts for the _PA_HEARTBEAT segment "
            "(feat-394 decision 6)"
        )
