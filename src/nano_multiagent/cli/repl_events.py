"""REPL helpers for async run polling and SSE event preview rendering."""

import json
from typing import TextIO

from nano_multiagent.cli.http_client import ServerClient

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
_EVENT_PREVIEW_MAX_LEN = 120
_EVENT_POLL_MAX_EVENTS = 200
_EVENT_POLL_TIMEOUT_SECONDS = 0.25


def send_message_with_async_events(
    *,
    out: TextIO,
    client: ServerClient,
    session_id: str,
    text: str,
) -> dict[str, object]:
    """Send message through async endpoint and stream incremental event previews."""
    submitted = client.send_message_async(session_id=session_id, text=text)
    run_id = _extract_run_id(submitted)
    seen_event_ids: set[str] = set()
    assistant_text = ""
    terminal_run: dict[str, object] | None = None

    while True:
        events = client.stream_session_events(
            session_id=session_id,
            max_events=_EVENT_POLL_MAX_EVENTS,
            timeout_seconds=_EVENT_POLL_TIMEOUT_SECONDS,
        )
        assistant_text, _ = consume_async_run_events(
            out=out,
            events=events,
            run_id=run_id,
            seen_event_ids=seen_event_ids,
            assistant_text=assistant_text,
        )

        run_payload = client.get_run(run_id=run_id)
        status_text = str(run_payload.get("status", "")).strip().lower()
        if status_text in _TERMINAL_RUN_STATUSES:
            terminal_run = run_payload
            break

    if terminal_run is None:
        raise RuntimeError("missing terminal async run result")

    if str(terminal_run.get("status", "")).strip().lower() != "completed":
        error_payload = terminal_run.get("error")
        raise RuntimeError(f"run_id={run_id} run failed: {error_payload}")

    return {
        "session_id": session_id,
        "run_id": run_id,
        "turn_id": terminal_run.get("turn_id"),
        "message": {
            "role": "assistant",
            "content": assistant_text,
        },
        "completed": True,
        "stop_reason": terminal_run.get("stop_reason") or "stop",
        "usage": terminal_run.get("usage"),
    }


def supports_async_repl_events(client: ServerClient) -> bool:
    """Check whether client supports async run APIs required by REPL event mode."""
    required_methods = ("send_message_async", "stream_session_events", "get_run")
    for name in required_methods:
        method = getattr(client, name, None)
        if not callable(method):
            return False
    return True


def _extract_run_id(payload: dict[str, object]) -> str:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise RuntimeError("missing run_id in async response")
    return run_id


def _normalize_session_event(event: object) -> tuple[str, str, dict[str, object]]:
    if not isinstance(event, dict):
        return "", "message", {}
    event_id = event.get("event_id")
    event_name = event.get("event")
    data = event.get("data")
    resolved_id = event_id.strip() if isinstance(event_id, str) else ""
    resolved_name = event_name.strip() if isinstance(event_name, str) and event_name.strip() else "message"
    resolved_data = data if isinstance(data, dict) else {}
    return resolved_id, resolved_name, resolved_data


def consume_async_run_events(
    *,
    out: TextIO,
    events: list[dict[str, object]],
    run_id: str,
    seen_event_ids: set[str],
    assistant_text: str,
) -> tuple[str, int]:
    """Consume one poll batch with dedupe and run-id filtering.

    Notes:
        Event id dedupe avoids replayed-history duplicates, and run-id filtering
        prevents cross-run events from polluting the current REPL turn.
    """
    delayed_terminal_run_status: dict[str, object] | None = None
    consumed = 0
    updated_text = assistant_text
    for event in events:
        event_id, event_name, data = _normalize_session_event(event)
        if event_id and event_id in seen_event_ids:
            continue
        if event_id:
            seen_event_ids.add(event_id)
        if data.get("run_id") != run_id:
            continue
        consumed += 1
        if event_name == "run_status":
            status = data.get("status")
            if isinstance(status, str) and status.strip().lower() in _TERMINAL_RUN_STATUSES:
                delayed_terminal_run_status = data
                continue
        print_event_preview(out=out, event_name=event_name, data=data)
        if event_name == "text_delta":
            delta = data.get("delta")
            if isinstance(delta, str):
                updated_text = merge_text_delta(updated_text, delta)
    if delayed_terminal_run_status is not None:
        print_event_preview(out=out, event_name="run_status", data=delayed_terminal_run_status)
    return updated_text, consumed


def print_event_preview(*, out: TextIO, event_name: str, data: dict[str, object]) -> None:
    """Render concise human-readable preview for one streamed event."""
    if event_name == "run_status":
        run_id = data.get("run_id")
        status = data.get("status")
        resolved_run_id = str(run_id) if isinstance(run_id, str) and run_id.strip() else "<unknown>"
        resolved_status = str(status) if isinstance(status, str) and status.strip() else "<unknown>"
        retry_preview = _format_retry_progress(data)
        if retry_preview:
            print(f"[run {resolved_run_id}] status={resolved_status} {retry_preview}", file=out, flush=True)
        else:
            print(f"[run {resolved_run_id}] status={resolved_status}", file=out, flush=True)
        return

    if event_name == "tool_start":
        name = data.get("name")
        arguments = data.get("arguments")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        print(
            f"[tool {resolved_name}] start args={_preview_event_value(arguments)}",
            file=out,
            flush=True,
        )
        return

    if event_name == "tool_end":
        name = data.get("name")
        error = data.get("error")
        output = data.get("output")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        if error not in (None, "", {}):
            print(f"[tool {resolved_name}] error={_preview_event_value(error)}", file=out, flush=True)
            return
        print(f"[tool {resolved_name}] output={_preview_event_value(output)}", file=out, flush=True)
        return

    if event_name == "text_delta":
        delta = data.get("delta")
        if isinstance(delta, str) and delta.strip():
            print(f"[text] {_preview_event_value(delta)}", file=out, flush=True)
        return


def _preview_event_value(value: object) -> str:
    if isinstance(value, dict):
        candidate = value.get("text")
        if isinstance(candidate, str):
            value = candidate
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    if len(text) <= _EVENT_PREVIEW_MAX_LEN:
        return text
    return f"{text[:_EVENT_PREVIEW_MAX_LEN]}..."


def _format_retry_progress(data: dict[str, object]) -> str:
    attempt = data.get("attempt")
    next_delay = data.get("next_delay")
    cooldown = data.get("cooldown")
    last_error = data.get("last_error")

    parts: list[str] = []
    if isinstance(attempt, int):
        parts.append(f"attempt={attempt}")
    if isinstance(next_delay, (int, float)):
        parts.append(f"next_delay={float(next_delay):.1f}s")
    if isinstance(cooldown, (int, float)) and float(cooldown) > 0:
        parts.append(f"cooldown={float(cooldown):.1f}s")
    if isinstance(last_error, dict):
        code = last_error.get("code")
        message = last_error.get("message")
        if isinstance(code, str) and isinstance(message, str):
            parts.append(f"last_error={code}:{_preview_event_value(message)}")
        elif isinstance(message, str):
            parts.append(f"last_error={_preview_event_value(message)}")
    return " ".join(parts)


def merge_text_delta(current: str, delta: str) -> str:
    """Merge text delta with full-text fallback behavior."""
    if not current:
        return delta
    if delta.startswith(current):
        return delta
    return f"{current}{delta}"
