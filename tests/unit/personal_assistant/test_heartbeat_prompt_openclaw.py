"""Tests for feat-394-M1 R3: HEARTBEAT_OK silence token + openclaw prompt verbatim parity.

Covers two exit criteria from M1:
1. HEARTBEAT_OK must be recognised as a silence token (same as NO_REPLY in heartbeat context).
2. _PA_HEARTBEAT prompt segment text must be verbatim identical to openclaw buildHeartbeatSection.

These tests are red until R3 implementation lands.
"""

from __future__ import annotations

# refactor-406-M2: products/ dissolved; the _PA_HEARTBEAT verbatim text lives in the
# PA production factory (personal_assistant.product). This verbatim parity test守的是
# 真实生产段（与 golden 同源）。
from personal_assistant.product import _PA_HEARTBEAT_TEXT  # noqa: PLC2701


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

    def test_heartbeat_segment_contains_heartbeat_ok_token(self) -> None:
        """The segment text must contain the exact HEARTBEAT_OK token string."""
        assert "HEARTBEAT_OK" in _PA_HEARTBEAT_TEXT

    def test_heartbeat_segment_verbatim_openclaw_lines(self) -> None:
        """Each line from openclaw buildHeartbeatSection must appear verbatim in the segment.

        Provenance: openclaw/src/agents/system-prompt.ts:124-138
        """
        text = _PA_HEARTBEAT_TEXT
        for line in self._EXPECTED_LINES:
            assert line in text, (
                f"Expected openclaw-verbatim line not found in _PA_HEARTBEAT_TEXT:\n"
                f"  Missing: {line!r}\n"
                f"  Actual segment:\n{text}"
            )

    def test_heartbeat_segment_provenance_comment_in_source(self) -> None:
        """The PA factory module must contain a Provenance comment pointing to openclaw.

        feat-394 decision 6: code comment convention requires 'Provenance:' annotation
        with openclaw source file and line number.
        """
        import inspect
        import personal_assistant.product as pa_module

        source = inspect.getsource(pa_module)
        # The comment must reference openclaw source path (system-prompt.ts)
        assert "openclaw" in source and "system-prompt.ts" in source, (
            "personal_assistant.product must contain a 'Provenance:' comment referencing "
            "openclaw/src/agents/system-prompt.ts for the _PA_HEARTBEAT segment "
            "(feat-394 decision 6)"
        )


# ---------------------------------------------------------------------------
# feat-394-M3 WARNING-2: _build_heartbeat_message 逐字照抄 openclaw HEARTBEAT_PROMPT
# ---------------------------------------------------------------------------


class TestHeartbeatMessageOpenclawVerbatim:
    """_build_heartbeat_message must embed the verbatim openclaw HEARTBEAT_PROMPT.

    Provenance: openclaw/src/auto-reply/heartbeat.ts:14
    HEARTBEAT_PROMPT = "Read HEARTBEAT.md if it exists (workspace context). Follow it
    strictly. Do not infer or repeat old tasks from prior chats. If nothing needs
    attention, reply HEARTBEAT_OK."

    feat-394 decision 6: heartbeat trigger message must use this verbatim text, not a
    custom rewording, so model behaviour matches openclaw expectations.
    """

    # Verbatim from openclaw/src/auto-reply/heartbeat.ts:14
    HEARTBEAT_PROMPT_VERBATIM = (
        "Read HEARTBEAT.md if it exists (workspace context). "
        "Follow it strictly. "
        "Do not infer or repeat old tasks from prior chats. "
        "If nothing needs attention, reply HEARTBEAT_OK."
    )

    def _call_build_message(self) -> str:
        from datetime import UTC, datetime
        from personal_assistant.scheduler.heartbeat_scheduler import (
            _build_heartbeat_message,
        )  # noqa: PLC2701

        return _build_heartbeat_message(
            agent_id="test-agent",
            due_at=datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC),
            instructions="",
        )

    def test_heartbeat_message_contains_openclaw_heartbeat_prompt(self) -> None:
        """_build_heartbeat_message must include the openclaw HEARTBEAT_PROMPT verbatim.

        Currently fails because _build_heartbeat_message uses a custom rewording.
        feat-394-M3 WARNING-2 / decision 6 fix.
        """
        message = self._call_build_message()
        assert self.HEARTBEAT_PROMPT_VERBATIM in message, (
            f"_build_heartbeat_message must embed the verbatim openclaw HEARTBEAT_PROMPT "
            f"(feat-394 decision 6 / WARNING-2):\n"
            f"  Expected to contain: {self.HEARTBEAT_PROMPT_VERBATIM!r}\n"
            f"  Actual message:\n{message}"
        )

    def test_heartbeat_message_provenance_comment_in_source(self) -> None:
        """heartbeat_scheduler.py must contain a Provenance comment for HEARTBEAT_PROMPT.

        feat-394 decision 6: code comment must reference openclaw source file and line.
        """
        import inspect
        import personal_assistant.scheduler.heartbeat_scheduler as hs_module

        source = inspect.getsource(hs_module)
        assert "openclaw/src/auto-reply/heartbeat.ts" in source, (
            "heartbeat_scheduler.py must contain a 'Provenance:' comment referencing "
            "openclaw/src/auto-reply/heartbeat.ts for HEARTBEAT_PROMPT "
            "(feat-394 decision 6)"
        )
