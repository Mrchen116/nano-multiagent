"""REPL helpers for async run polling and SSE event preview rendering."""

import json
from typing import Callable
from typing import TextIO

from coding_cli.events.event_pipeline import replay_fallback_dedupe_key

_EVENT_PREVIEW_MAX_LEN = 120
_EVENT_PREVIEW_HEAD_LEN = 72
_EVENT_PREVIEW_TAIL_LEN = 45
_EVENT_POLL_MAX_EVENTS = 200
_EVENT_POLL_TIMEOUT_SECONDS = 0.25


def print_event_preview(
    *, out: TextIO, event_name: str, data: dict[str, object]
) -> None:
    """Render concise human-readable preview for one streamed event."""
    line = _event_preview_line(event_name=event_name, data=data)
    if line is not None:
        print(line, file=out, flush=True)


def _emit_preview_line(
    *,
    out: TextIO,
    event_name: str,
    data: dict[str, object],
    preview_writer: Callable[[str], None] | None,
) -> str | None:
    line = _event_preview_line(event_name=event_name, data=data)
    if line is None:
        return None
    if preview_writer is not None:
        preview_writer(line)
        return line
    print(line, file=out, flush=True)
    return line


def _build_ordered_repl_updates(
    events: list[tuple[str, dict[str, object]]],
) -> list[dict[str, str]]:
    updates: list[dict[str, str]] = []
    assistant_buffer = ""
    pending_tool_identity: str | None = None
    pending_tool_line: str | None = None

    def _flush_assistant() -> None:
        nonlocal assistant_buffer
        if assistant_buffer:
            updates.append({"kind": "assistant", "text": assistant_buffer})
            assistant_buffer = ""

    def _flush_tool() -> None:
        nonlocal pending_tool_identity, pending_tool_line
        if pending_tool_line:
            updates.append({"kind": "tool", "text": pending_tool_line})
        pending_tool_identity = None
        pending_tool_line = None

    for event_name, data in events:
        if event_name == "text_delta":
            delta = data.get("delta")
            if isinstance(delta, str) and delta:
                _flush_tool()
                assistant_buffer = merge_text_delta(assistant_buffer, delta)
            continue

        tool_line = _ordered_tool_update_line(event_name=event_name, data=data)
        if tool_line is None:
            continue
        tool_identity = _ordered_tool_identity(event_name=event_name, data=data)
        if pending_tool_identity is not None and pending_tool_identity != tool_identity:
            _flush_tool()
        _flush_assistant()
        pending_tool_identity = tool_identity
        pending_tool_line = tool_line

    _flush_tool()
    _flush_assistant()
    assistant_count = sum(1 for item in updates if item["kind"] == "assistant")
    has_tool = any(item["kind"] == "tool" for item in updates)
    if assistant_count >= 2 and has_tool:
        return updates
    return []


def _ordered_tool_update_line(
    *, event_name: str, data: dict[str, object]
) -> str | None:
    preview = _event_preview_line(event_name=event_name, data=data)
    if preview is None:
        return None
    if not preview.startswith("Tool:"):
        return None
    return preview


def _ordered_tool_identity(*, event_name: str, data: dict[str, object]) -> str:
    call_id = data.get("call_id")
    if isinstance(call_id, str) and call_id.strip():
        return call_id
    name = data.get("name")
    if isinstance(name, str) and name.strip():
        return f"{name}:{event_name}"
    return event_name


def _event_preview_line(*, event_name: str, data: dict[str, object]) -> str | None:
    if event_name == "run_status":
        run_id = data.get("run_id")
        status = data.get("status")
        resolved_run_id = (
            str(run_id) if isinstance(run_id, str) and run_id.strip() else "<unknown>"
        )
        resolved_status = (
            str(status) if isinstance(status, str) and status.strip() else "<unknown>"
        )
        retry_preview = _format_retry_progress(data)
        if retry_preview:
            return f"Run {resolved_run_id}: status={resolved_status} {retry_preview}"
        return f"Run {resolved_run_id}: status={resolved_status}"

    if event_name == "tool_start":
        name = data.get("name")
        arguments = data.get("arguments")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        return _with_call_id_preview(
            f"Tool: {resolved_name} start args={_preview_event_value(arguments)}",
            data=data,
        )

    if event_name == "tool_end":
        name = data.get("name")
        error = data.get("error")
        output = data.get("output")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        if error not in (None, "", {}):
            return _with_call_id_preview(
                f"Tool: {resolved_name} error={_preview_event_value(error)}", data=data
            )
        return _with_call_id_preview(
            f"Tool: {resolved_name} output={_preview_event_value(output)}", data=data
        )

    if event_name == "tool_exec_started":
        name = data.get("name")
        status = data.get("status")
        elapsed_ms = data.get("elapsed_ms")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        resolved_status = (
            str(status) if isinstance(status, str) and status.strip() else "started"
        )
        resolved_elapsed = _preview_elapsed_ms(elapsed_ms)
        return _with_call_id_preview(
            f"Tool: {resolved_name} started status={resolved_status} elapsed={resolved_elapsed}",
            data=data,
        )

    if event_name == "tool_exec_running":
        name = data.get("name")
        status = data.get("status")
        elapsed_ms = data.get("elapsed_ms")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        resolved_status = (
            str(status) if isinstance(status, str) and status.strip() else "running"
        )
        resolved_elapsed = _preview_elapsed_ms(elapsed_ms)
        return _with_call_id_preview(
            f"Tool: {resolved_name} running status={resolved_status} elapsed={resolved_elapsed}",
            data=data,
        )

    if event_name == "tool_exec_chunk":
        name = data.get("name")
        stream = data.get("stream")
        chunk = data.get("chunk")
        seq = data.get("seq")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        resolved_stream = (
            str(stream) if isinstance(stream, str) and stream.strip() else "<unknown>"
        )
        resolved_seq = str(seq) if isinstance(seq, int) else "?"
        return _with_call_id_preview(
            f"Tool: {resolved_name} chunk {resolved_stream}#{resolved_seq}: {_preview_event_value(chunk)}",
            data=data,
        )

    if event_name == "tool_exec_exit":
        name = data.get("name")
        status = data.get("status")
        duration_ms = data.get("duration_ms")
        exit_code = data.get("exit_code")
        resolved_name = (
            str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        )
        resolved_status = (
            str(status) if isinstance(status, str) and status.strip() else "<unknown>"
        )
        resolved_duration = _preview_elapsed_ms(duration_ms)
        resolved_exit_code = (
            str(exit_code) if isinstance(exit_code, int) else "<unknown>"
        )
        line = (
            f"Tool: {resolved_name} exit code={resolved_exit_code} "
            f"status={resolved_status} duration={resolved_duration}"
        )
        return _with_call_id_preview(line, data=data)

    if event_name == "text_delta":
        delta = data.get("delta")
        if isinstance(delta, str) and delta.strip():
            return f"Text: {_preview_event_value(delta)}"
    return None


def _format_status_progress(data: dict[str, object]) -> str:
    status = data.get("status")
    resolved_status = (
        str(status).strip().lower()
        if isinstance(status, str) and status.strip()
        else "<unknown>"
    )
    retry_preview = _format_retry_progress(data)
    if resolved_status in {"queued", "running", "completed"} and not retry_preview:
        return ""
    if resolved_status == "completed":
        return ""
    if resolved_status == "running" and retry_preview:
        return f"retrying ({retry_preview})"
    if resolved_status == "queued" and retry_preview:
        return f"queued ({retry_preview})"
    if retry_preview:
        return f"{resolved_status} ({retry_preview})"
    return resolved_status


def _preview_event_value(value: object) -> str:
    if isinstance(value, dict):
        candidate = value.get("text")
        if isinstance(candidate, str):
            value = candidate
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    if len(text) <= _EVENT_PREVIEW_MAX_LEN:
        return text
    head_len = _EVENT_PREVIEW_HEAD_LEN
    tail_len = _EVENT_PREVIEW_TAIL_LEN
    if head_len + tail_len + 3 > _EVENT_PREVIEW_MAX_LEN:
        head_len = (_EVENT_PREVIEW_MAX_LEN - 3) // 2
        tail_len = _EVENT_PREVIEW_MAX_LEN - 3 - head_len
    return f"{text[:head_len]}...{text[-tail_len:]}"


def _format_retry_progress(data: dict[str, object]) -> str:
    attempt = data.get("attempt")
    next_delay = data.get("next_delay")
    cooldown = data.get("cooldown")
    last_error = data.get("last_error")

    parts: list[str] = []
    if isinstance(attempt, int):
        parts.append(f"attempt {attempt}")
    if isinstance(next_delay, (int, float)):
        parts.append(f"next {float(next_delay):.1f}s")
    if isinstance(cooldown, (int, float)) and float(cooldown) > 0:
        parts.append(f"cooldown {float(cooldown):.1f}s")
    if isinstance(last_error, dict):
        code = last_error.get("code")
        message = last_error.get("message")
        if isinstance(code, str) and isinstance(message, str):
            parts.append(f"last error {code}: {_preview_event_value(message)}")
        elif isinstance(message, str):
            parts.append(f"last error {_preview_event_value(message)}")
    return ", ".join(parts)


def merge_text_delta(current: str, delta: str) -> str:
    """Merge text delta with full-text fallback behavior."""
    if not current:
        return delta
    if delta.startswith(current):
        return delta
    return f"{current}{delta}"


def _event_replay_dedupe_key(*, event_name: str, data: dict[str, object]) -> str | None:
    return replay_fallback_dedupe_key(event_name=event_name, data=data)


def _filter_previewed_tool_updates(
    *, tool_updates: list[str], previewed_tool_lines: set[str]
) -> list[str]:
    if not previewed_tool_lines:
        return tool_updates
    previewed_identities = {_tool_line_identity(line) for line in previewed_tool_lines}
    previewed_identities.discard("")
    if not previewed_identities:
        return tool_updates

    result: list[str] = []
    for line in tool_updates:
        identity = _tool_line_identity(line)
        if identity and identity in previewed_identities:
            continue
        result.append(line)
    return result


def _tool_line_identity(line: str) -> str:
    trimmed = line.strip()
    if trimmed.startswith("Tool:"):
        return trimmed[5:].strip()
    if trimmed.startswith("Tool "):
        return trimmed[5:].strip()
    return trimmed


def _tool_preview_identity(
    *, event_name: str, data: dict[str, object], run_id: str
) -> str | None:
    phase_by_event = {
        "tool_start": "start",
        "tool_exec_started": "started",
        "tool_exec_exit": "exit",
    }
    phase = phase_by_event.get(event_name)
    if phase is None:
        return None

    name = _tool_name_from_data(data)
    if not name:
        return None

    raw_call_id = data.get("call_id")
    if isinstance(raw_call_id, str) and raw_call_id.strip():
        call_id = raw_call_id.strip()
    else:
        call_id = "<missing-call-id>"
    return f"{run_id}|{name}|{call_id}|{phase}"


def _is_live_preview_event(event_name: str) -> bool:
    return event_name in {"tool_start", "tool_exec_started", "tool_exec_exit"}


def _preview_elapsed_ms(value: object) -> str:
    if isinstance(value, int):
        return f"{value}ms"
    if isinstance(value, float):
        return f"{int(value)}ms"
    return "unknown"


def _tool_name_from_data(data: dict[str, object]) -> str:
    raw = data.get("name")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _tool_group_key(data: dict[str, object]) -> str:
    name = _tool_name_from_data(data)
    if not name:
        return ""
    call_id = data.get("call_id")
    if isinstance(call_id, str) and call_id.strip():
        return f"{name}::{call_id.strip()}"
    return name


def _with_call_id_preview(line: str, *, data: dict[str, object]) -> str:
    call_id = data.get("call_id")
    if not isinstance(call_id, str):
        return line
    resolved = call_id.strip()
    if not resolved:
        return line
    return f"{line} [call_id={resolved}]"
