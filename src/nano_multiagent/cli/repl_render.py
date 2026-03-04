"""Structured REPL turn rendering helpers."""

from typing import TextIO

from nano_multiagent.cli.context_budget import print_context_budget_snapshot


def print_repl_turn_summary(
    *,
    out: TextIO,
    payload: dict[str, object],
    context_budget_client: object | None = None,
) -> None:
    """Render one turn result with compact answer-first summary."""
    run_id = _read_non_empty_str(payload.get("run_id"))
    session_id = _read_non_empty_str(payload.get("session_id"))
    state = _resolve_state(payload)
    stop_reason = _read_non_empty_str(payload.get("stop_reason"))
    view = payload.get("_repl_view")
    status_updates: list[str] = []
    tool_updates: list[str] = []
    if isinstance(view, dict):
        status_updates = _as_non_empty_str_list(view.get("status_updates"))
        tool_updates = _as_non_empty_str_list(view.get("tool_updates"))
    answer = _extract_message_content(payload)
    usage_line = _format_usage_line(payload.get("usage"))
    compact_status_updates = _compact_status_updates(status_updates, final_state=state)
    compact_tool_updates = _compact_tool_updates(tool_updates)

    print("Assistant:", file=out)
    if answer is not None:
        print(answer, file=out)
    else:
        print("(empty)", file=out)

    status_parts: list[str] = [state]
    if stop_reason is not None:
        status_parts.append(f"stop={stop_reason}")
    if run_id is not None:
        status_parts.append(f"run={run_id}")
    if session_id is not None:
        status_parts.append(f"session={session_id}")
    print(f"State: {' | '.join(status_parts)}", file=out)
    for update in compact_status_updates:
        print(f"Progress: {update}", file=out)
    for update in compact_tool_updates:
        print(f"Tool: {update}", file=out)

    print(f"Usage: {usage_line}", file=out)

    if context_budget_client is not None and session_id is not None:
        print_context_budget_snapshot(out=out, client=context_budget_client, session_id=session_id)


def print_repl_turn_error(
    *,
    out: TextIO,
    error: Exception,
    layer: str,
    suggestion: str,
) -> None:
    """Render one failed turn with compact answer-first summary."""
    print("Assistant: (empty)", file=out)
    print(f"State: failed | layer={layer}", file=out)
    print(f"Error: {error}", file=out)
    print(f"Hint: suggestion={suggestion}", file=out)
    print("Usage: unavailable", file=out)


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


def _extract_message_content(payload: dict[str, object]) -> str | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    return None


def _format_usage_line(usage: object) -> str:
    if not isinstance(usage, dict):
        return "unavailable"
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if all(isinstance(value, int) for value in (prompt, completion, total)):
        return f"prompt={prompt}, completion={completion}, total={total}"
    return "unavailable"


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
