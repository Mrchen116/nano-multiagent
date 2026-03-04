"""Structured REPL turn rendering helpers."""

from typing import TextIO

from nano_multiagent.cli.context_budget import print_context_budget_snapshot


def print_repl_turn_summary(
    *,
    out: TextIO,
    payload: dict[str, object],
    context_budget_client: object | None = None,
) -> None:
    """Render one turn result with status/tools/answer/error/usage sections."""
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

    print("Status:", file=out)
    if session_id is not None:
        print(f"- session_id={session_id}", file=out)
    if run_id is not None:
        print(f"- run_id={run_id}", file=out)
    print(f"- state={state}", file=out)
    if stop_reason is not None:
        print(f"- stop_reason={stop_reason}", file=out)
    for update in status_updates:
        print(f"- {update}", file=out)

    print("Tools:", file=out)
    if tool_updates:
        for update in tool_updates:
            print(f"- {update}", file=out)
    else:
        print("- (none)", file=out)

    print("Answer:", file=out)
    if answer is not None:
        print(answer, file=out)
    else:
        print("(empty)", file=out)

    print("Usage:", file=out)
    print(f"- {usage_line}", file=out)

    if context_budget_client is not None and session_id is not None:
        print_context_budget_snapshot(out=out, client=context_budget_client, session_id=session_id)


def print_repl_turn_error(
    *,
    out: TextIO,
    error: Exception,
    layer: str,
    suggestion: str,
) -> None:
    """Render one failed turn with structured sections."""
    print("Status:", file=out)
    print("- state=failed", file=out)
    print("Tools:", file=out)
    print("- (none)", file=out)
    print("Answer:", file=out)
    print("(empty)", file=out)
    print("Error:", file=out)
    print(f"- {error}", file=out)
    print(f"- layer={layer}", file=out)
    print(f"- suggestion={suggestion}", file=out)
    print("Usage:", file=out)
    print("- unavailable", file=out)


def _resolve_state(payload: dict[str, object]) -> str:
    status = _read_non_empty_str(payload.get("status"))
    if status is not None:
        return status
    if payload.get("completed") is True:
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
