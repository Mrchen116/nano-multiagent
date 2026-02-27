from dataclasses import dataclass

from .types import CompactionReason


@dataclass(frozen=True, slots=True)
class CompactionDecision:
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
