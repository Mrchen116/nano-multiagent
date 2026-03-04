"""LLM usage presentation helpers for interactive CLI feedback."""

from typing import TextIO


def print_turn_usage_snapshot(*, out: TextIO, payload: object) -> None:
    """Print per-turn model usage when available."""
    metrics = extract_turn_usage_metrics(payload)
    if metrics is None:
        return
    prompt_tokens, completion_tokens, total_tokens = metrics
    print(
        (
            "LLM usage (this turn): "
            f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
        ),
        file=out,
    )


def extract_turn_usage_metrics(payload: object) -> tuple[int, int, int] | None:
    """Extract canonical per-turn usage counters from response payload."""
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if not _is_non_negative_int(prompt_tokens):
        return None
    if not _is_non_negative_int(completion_tokens):
        return None
    if _is_non_negative_int(total_tokens):
        resolved_total = int(total_tokens)
    else:
        resolved_total = int(prompt_tokens) + int(completion_tokens)
    return int(prompt_tokens), int(completion_tokens), resolved_total


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
