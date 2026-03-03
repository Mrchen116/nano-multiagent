"""Compaction decision policy based on context token budget."""

from dataclasses import dataclass

from .types import CompactionReason


@dataclass(frozen=True, slots=True)
class CompactionDecision:
    """Capture the policy decision and token-budget context."""

    reason: CompactionReason
    context_tokens: int
    context_window: int
    reserve_tokens: int


def should_compact(
    *,
    context_tokens: int,
    context_window: int,
    reserve_tokens: int,
) -> CompactionDecision | None:
    """Decide whether compaction should run for current context usage.

    Args:
        context_tokens: Estimated tokens currently in context.
        context_window: Model context window size.
        reserve_tokens: Tokens reserved for the next response.

    Returns:
        A decision when threshold/overflow is reached, otherwise `None`.
    """

    if context_window <= 0:
        return None
    if context_tokens > context_window:
        return CompactionDecision(
            reason=CompactionReason.OVERFLOW,
            context_tokens=context_tokens,
            context_window=context_window,
            reserve_tokens=reserve_tokens,
        )
    threshold = max(context_window - max(reserve_tokens, 0), 0)
    if context_tokens >= threshold:
        return CompactionDecision(
            reason=CompactionReason.THRESHOLD,
            context_tokens=context_tokens,
            context_window=context_window,
            reserve_tokens=reserve_tokens,
        )
    return None
