"""Classify agent text before Gateway delivery makes it user-visible."""

from __future__ import annotations

from enum import StrEnum


class ReplyVisibilityPolicy(StrEnum):
    """Define whether protocol silence tokens are literal text or control signals."""

    LITERAL_TEXT = "literal_text"
    SUPPRESS_PROTOCOL_TOKENS = "suppress_protocol_tokens"


_PROTOCOL_SILENCE_TOKENS = frozenset({"NO_REPLY", "HEARTBEAT_OK"})


def is_protocol_silence_token(text: str) -> bool:
    """Return whether text is an exact protocol silence token after trimming.

    Args:
        text: Complete assistant message content, not a partial token delta.

    Returns:
        True only for a recognized silence token; surrounding whitespace is ignored.
    """

    return text.strip() in _PROTOCOL_SILENCE_TOKENS


def should_suppress_reply(text: str, *, policy: ReplyVisibilityPolicy) -> bool:
    """Decide whether complete assistant text must remain invisible.

    Args:
        text: Complete assistant message content.
        policy: Delivery policy chosen from the originating run context.

    Returns:
        True when the policy treats the text as a control signal rather than content.
    """

    return (
        policy is ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
        and is_protocol_silence_token(text)
    )
