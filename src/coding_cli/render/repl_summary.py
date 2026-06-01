"""Minimal REPL turn summary formatter shared by TTY and non-TTY paths."""

from typing import TextIO

from coding_cli.render.context_budget import print_context_budget_snapshot
from coding_cli.render.turn_usage import extract_turn_usage_metrics


def _extract_message_content(payload: dict[str, object]) -> str | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content


def format_turn_summary(
    *,
    payload: dict[str, object],
    context_budget_client: object | None = None,
) -> str:
    """Build a minimal, human-readable turn summary.

    Intentionally omits run_id and session_id from the default view to reduce
    machine noise.
    """
    state = _resolve_state(payload)
    stop_reason = _read_non_empty_str(payload.get("stop_reason"))
    usage_line = _format_usage_line(payload.get("usage"))
    view = payload.get("_repl_view")
    status_updates: list[str] = []
    tool_updates: list[str] = []
    if isinstance(view, dict):
        status_updates = _as_non_empty_str_list(view.get("status_updates"))
        tool_updates = _as_non_empty_str_list(view.get("tool_updates"))
    compact_status_updates = _compact_status_updates(status_updates, final_state=state)
    compact_tool_updates = _compact_tool_updates(tool_updates)
    ordered_rendered = bool(payload.get("_ordered_rendered"))

    lines: list[str] = []
    status_parts: list[str] = [state]
    if stop_reason is not None:
        status_parts.append(f"stop={stop_reason}")
    lines.append(f"State: {' | '.join(status_parts)}")
    for update in compact_status_updates:
        lines.append(f"Progress: {update}")
    if not payload.get("_live_rendered") and not ordered_rendered:
        for update in compact_tool_updates:
            lines.append(f"Tool: {update}")
    lines.append(f"Usage: {usage_line}")

    return "\n".join(lines)


def print_turn_summary(
    *,
    out: TextIO,
    payload: dict[str, object],
    context_budget_client: object | None = None,
) -> None:
    """Render the minimal turn summary to the output stream."""
    summary = format_turn_summary(payload=payload)
    if summary:
        print(summary, file=out)
    session_id = _read_non_empty_str(payload.get("session_id"))
    if context_budget_client is not None and session_id is not None:
        print_context_budget_snapshot(
            out=out, client=context_budget_client, session_id=session_id
        )


def _resolve_state(payload: dict[str, object]) -> str:
    status = _read_non_empty_str(payload.get("status"))
    if status is not None:
        return status
    if payload.get("completed") is True:
        return "completed"
    if _read_non_empty_str(payload.get("stop_reason")) is not None:
        return "completed"
    return "unknown"


def _read_non_empty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _as_non_empty_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item)
    return result


def _format_usage_line(usage: object) -> str:
    metrics = extract_turn_usage_metrics({"usage": usage})
    if metrics is None:
        return "unavailable"
    prompt_tokens, completion_tokens, total_tokens = metrics
    return (
        f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
    )


def _compact_status_updates(updates: list[str], *, final_state: str) -> list[str]:
    latest: str | None = None
    for raw in updates:
        line = raw.strip()
        if not line:
            continue
        if line == f"status={final_state}":
            continue
        latest = line
    if latest is None:
        return []
    return [latest]


def _compact_tool_updates(updates: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in updates:
        normalized = _normalize_tool_update(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    if len(result) <= 4:
        return result
    return result[-4:]


def _normalize_tool_update(line: str) -> str:
    trimmed = line.strip()
    if not trimmed:
        return ""
    if trimmed.startswith("Tool:"):
        normalized = trimmed[5:].strip()
        if normalized:
            return normalized
    if trimmed.startswith("Tool "):
        normalized = trimmed[5:].strip()
        if normalized:
            return normalized
    if trimmed.startswith("[tool ") and "] " in trimmed:
        closing = trimmed.find("] ")
        name = trimmed[6:closing].strip()
        remainder = trimmed[closing + 2 :].strip()
        if name and remainder:
            return f"{name} {remainder}"
    return trimmed
