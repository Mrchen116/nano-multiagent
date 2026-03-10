"""Context-budget presentation helpers for interactive CLI feedback."""

from typing import TextIO

from nano_multiagent.apps.coding_cli.client import ServerClient

_SHORT_ERROR_MAX_LEN = 120
_CONTEXT_BUDGET_HINTS = (
    (0.95, "Budget hint: usage >= 95%, run /compact now."),
    (0.85, "Budget hint: usage >= 85%, consider /compact soon."),
    (0.70, "Budget hint: usage >= 70%, monitor context and consider /compact."),
)


def print_context_budget_snapshot(
    *,
    out: TextIO,
    client: ServerClient,
    session_id: str,
    context_label: str | None = None,
) -> None:
    """Print context usage summary and threshold hint when available."""
    getter = getattr(client, "get_context_budget", None)
    if not callable(getter):
        return
    prefix = context_budget_prefix(context_label)
    try:
        payload = getter(session_id=session_id)
    except Exception as exc:
        print(f"{prefix}: unavailable ({_short_error_text(exc)}).", file=out)
        return

    metrics = extract_context_budget_metrics(payload)
    if metrics is None:
        print(f"{prefix}: unavailable (invalid payload).", file=out)
        return
    used_tokens, max_tokens, usage_ratio = metrics
    print(f"{prefix}: {used_tokens}/{max_tokens} ({usage_ratio * 100:.1f}%)", file=out)
    hint = context_budget_hint_for_ratio(usage_ratio)
    if hint is not None:
        print(hint, file=out)


def context_budget_prefix(context_label: str | None) -> str:
    """Build display prefix for context budget lines."""
    if isinstance(context_label, str) and context_label.strip():
        return f"Context budget ({context_label.strip()})"
    return "Context budget"


def extract_context_budget_metrics(payload: object) -> tuple[int, int, float] | None:
    """Extract/normalize budget metrics from HTTP payload."""
    if not isinstance(payload, dict):
        return None
    used_tokens = payload.get("used_tokens")
    max_tokens = payload.get("max_tokens")
    usage_ratio = payload.get("usage_ratio")
    if isinstance(used_tokens, bool) or not isinstance(used_tokens, int):
        return None
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        return None

    resolved_ratio: float
    if isinstance(usage_ratio, bool):
        return None
    if isinstance(usage_ratio, (int, float)):
        resolved_ratio = float(usage_ratio)
    else:
        resolved_ratio = float(used_tokens) / float(max_tokens)
    if resolved_ratio < 0:
        resolved_ratio = 0.0
    if resolved_ratio > 1:
        resolved_ratio = 1.0
    return used_tokens, max_tokens, resolved_ratio


def context_budget_hint_for_ratio(usage_ratio: float) -> str | None:
    """Return first matching budget hint for usage ratio threshold."""
    for threshold, hint in _CONTEXT_BUDGET_HINTS:
        if usage_ratio >= threshold:
            return hint
    return None


def _short_error_text(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return "unknown error"
    if len(text) <= _SHORT_ERROR_MAX_LEN:
        return text
    return f"{text[:_SHORT_ERROR_MAX_LEN]}..."
