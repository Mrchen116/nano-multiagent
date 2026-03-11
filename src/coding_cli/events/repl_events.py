"""REPL helpers for async run polling and SSE event preview rendering."""

import json
from typing import Callable
from typing import TextIO

from coding_cli.client import ServerClient
from coding_cli.events.event_pipeline import EventDedupeWindow
from coding_cli.events.event_pipeline import ReplPerfTracker
from coding_cli.events.event_pipeline import ReplRenderPhaseMachine
from coding_cli.events.event_pipeline import build_repl_view_model as _build_repl_view_model_from_pipeline
from coding_cli.events.event_pipeline import consume_event_for_run as _consume_event_for_run
from coding_cli.events.event_pipeline import normalize_session_event as _normalize_session_event_from_pipeline
from coding_cli.events.event_pipeline import replay_fallback_dedupe_key

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
_EVENT_PREVIEW_MAX_LEN = 120
_EVENT_PREVIEW_HEAD_LEN = 72
_EVENT_PREVIEW_TAIL_LEN = 45
_EVENT_POLL_MAX_EVENTS = 200
_EVENT_POLL_TIMEOUT_SECONDS = 0.25


def send_message_with_async_events(
    *,
    out: TextIO,
    client: ServerClient,
    session_id: str,
    text: str,
    preview_writer: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Send message through async endpoint and aggregate structured turn view."""
    submitted = client.send_message_async(session_id=session_id, text=text)
    run_id = _extract_run_id(submitted)
    dedupe_window = EventDedupeWindow()
    perf_tracker = ReplPerfTracker()
    render_phase_machine = ReplRenderPhaseMachine()
    seen_event_ids: set[str] | None = None
    seen_event_fingerprints: set[str] | None = None
    assistant_text = ""
    terminal_run: dict[str, object] | None = None
    collected_events: list[tuple[str, dict[str, object]]] = []

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
            seen_event_fingerprints=seen_event_fingerprints,
            dedupe_window=dedupe_window,
            render_phase_machine=render_phase_machine,
            assistant_text=assistant_text,
            emit_preview=True,
            collected_events=collected_events,
            preview_writer=preview_writer,
            perf_tracker=perf_tracker,
        )

        run_payload = client.get_run(run_id=run_id)
        status_text = str(run_payload.get("status", "")).strip().lower()
        if status_text in _TERMINAL_RUN_STATUSES:
            terminal_run = run_payload
            render_phase_machine.begin_finalizing()
            break

    if terminal_run is None:
        raise RuntimeError("missing terminal async run result")

    if str(terminal_run.get("status", "")).strip().lower() != "completed":
        error_payload = terminal_run.get("error")
        raise RuntimeError(f"run_id={run_id} run failed: {error_payload}")

    if not render_phase_machine.can_build_final_summary():
        render_phase_machine.begin_finalizing()
    status_updates, tool_updates = _build_repl_view(collected_events)
    tool_updates = render_phase_machine.filter_summary_tool_updates(
        tool_updates,
        line_identity_resolver=_tool_line_identity,
    )
    render_phase_machine.mark_finalized()
    return {
        "session_id": session_id,
        "run_id": run_id,
        "turn_id": terminal_run.get("turn_id"),
        "message": {
            "role": "assistant",
            "content": assistant_text,
        },
        "status": terminal_run.get("status") or "completed",
        "completed": True,
        "stop_reason": terminal_run.get("stop_reason") or "stop",
        "usage": terminal_run.get("usage"),
        "_repl_view": {
            "status_updates": status_updates,
            "tool_updates": tool_updates,
            "perf_metrics": perf_tracker.snapshot(),
        },
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
    normalized_event = _normalize_session_event_from_pipeline(event)
    return normalized_event.event_id, normalized_event.event_name, normalized_event.data


def consume_async_run_events(
    *,
    out: TextIO,
    events: list[dict[str, object]],
    run_id: str,
    assistant_text: str,
    seen_event_ids: set[str] | None = None,
    seen_event_fingerprints: set[str] | None = None,
    dedupe_window: EventDedupeWindow | None = None,
    render_phase_machine: ReplRenderPhaseMachine | None = None,
    emit_preview: bool = True,
    collected_events: list[tuple[str, dict[str, object]]] | None = None,
    preview_writer: Callable[[str], None] | None = None,
    previewed_tool_lines: set[str] | None = None,
    emitted_tool_preview_identities: set[str] | None = None,
    perf_tracker: ReplPerfTracker | None = None,
) -> tuple[str, int]:
    """Consume one poll batch with dedupe and run-id filtering.

    Notes:
        Event id dedupe avoids replayed-history duplicates, and run-id filtering
        prevents cross-run events from polluting the current REPL turn.
    """
    delayed_terminal_run_status: dict[str, object] | None = None
    saw_terminal_run_status = False
    consumed = 0
    preview_emitted = 0
    dedupe_dropped = 0
    run_filtered = 0
    polled_events = len(events)
    updated_text = assistant_text
    resolved_dedupe_window = dedupe_window or EventDedupeWindow()
    resolved_phase_machine = render_phase_machine or ReplRenderPhaseMachine()
    for event in events:
        normalized_event = _normalize_session_event_from_pipeline(event)
        event_name = normalized_event.event_name
        data = normalized_event.data
        if data.get("run_id") != run_id:
            run_filtered += 1
            continue
        if not _consume_event_for_run(
            normalized_event=normalized_event,
            run_id=run_id,
            dedupe_window=resolved_dedupe_window,
            seen_event_ids=seen_event_ids,
            seen_event_fingerprints=seen_event_fingerprints,
        ):
            dedupe_dropped += 1
            continue
        consumed += 1
        if event_name == "run_status":
            status = data.get("status")
            if isinstance(status, str) and status.strip().lower() in _TERMINAL_RUN_STATUSES:
                delayed_terminal_run_status = data
                saw_terminal_run_status = True
                continue
        if collected_events is not None:
            collected_events.append((event_name, data))
        if emit_preview and _is_live_preview_event(event_name) and resolved_phase_machine.can_emit_preview():
            preview_identity = _tool_preview_identity(event_name=event_name, data=data, run_id=run_id)
            should_emit_preview = resolved_phase_machine.should_emit_tool_preview(preview_identity)
            if emitted_tool_preview_identities is not None and preview_identity is not None:
                if preview_identity in emitted_tool_preview_identities:
                    should_emit_preview = False
            if (
                not should_emit_preview
            ):
                emitted_line = None
            else:
                emitted_line = _emit_preview_line(out=out, event_name=event_name, data=data, preview_writer=preview_writer)
                if emitted_line is not None:
                    preview_emitted += 1
                    preview_line_identity = _tool_line_identity(emitted_line) if event_name.startswith("tool_") else ""
                    resolved_phase_machine.record_tool_preview(
                        preview_identity=preview_identity,
                        preview_line_identity=preview_line_identity,
                    )
                    if preview_identity is not None and emitted_tool_preview_identities is not None:
                        emitted_tool_preview_identities.add(preview_identity)
            if previewed_tool_lines is not None and emitted_line is not None and event_name.startswith("tool_"):
                previewed_tool_lines.add(emitted_line)
        if event_name == "text_delta":
            delta = data.get("delta")
            if isinstance(delta, str):
                updated_text = merge_text_delta(updated_text, delta)
    if saw_terminal_run_status:
        resolved_phase_machine.begin_finalizing()
    if delayed_terminal_run_status is not None:
        if collected_events is not None:
            collected_events.append(("run_status", delayed_terminal_run_status))
        if emit_preview and _is_live_preview_event("run_status"):
            _emit_preview_line(
                out=out,
                event_name="run_status",
                data=delayed_terminal_run_status,
                preview_writer=preview_writer,
            )
    if perf_tracker is not None:
        perf_tracker.record_batch(
            polled_events=polled_events,
            consumed_events=consumed,
            preview_emitted=preview_emitted,
            run_filtered=run_filtered,
            dedupe_dropped=dedupe_dropped,
        )
    return updated_text, consumed


def print_event_preview(*, out: TextIO, event_name: str, data: dict[str, object]) -> None:
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


def _build_repl_view(events: list[tuple[str, dict[str, object]]]) -> tuple[list[str], list[str]]:
    model = _build_repl_view_model_from_pipeline(
        events=events,
        preview_line_resolver=lambda event_name, data: _event_preview_line(event_name=event_name, data=data),
        status_line_resolver=_format_status_progress,
    )
    return model.status_updates, model.tool_updates


def _event_preview_line(*, event_name: str, data: dict[str, object]) -> str | None:
    if event_name == "run_status":
        run_id = data.get("run_id")
        status = data.get("status")
        resolved_run_id = str(run_id) if isinstance(run_id, str) and run_id.strip() else "<unknown>"
        resolved_status = str(status) if isinstance(status, str) and status.strip() else "<unknown>"
        retry_preview = _format_retry_progress(data)
        if retry_preview:
            return f"Run {resolved_run_id}: status={resolved_status} {retry_preview}"
        return f"Run {resolved_run_id}: status={resolved_status}"

    if event_name == "tool_start":
        name = data.get("name")
        arguments = data.get("arguments")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        return _with_call_id_preview(
            f"Tool: {resolved_name} start args={_preview_event_value(arguments)}",
            data=data,
        )

    if event_name == "tool_end":
        name = data.get("name")
        error = data.get("error")
        output = data.get("output")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        if error not in (None, "", {}):
            return _with_call_id_preview(f"Tool: {resolved_name} error={_preview_event_value(error)}", data=data)
        return _with_call_id_preview(f"Tool: {resolved_name} output={_preview_event_value(output)}", data=data)

    if event_name == "tool_exec_started":
        name = data.get("name")
        status = data.get("status")
        elapsed_ms = data.get("elapsed_ms")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        resolved_status = str(status) if isinstance(status, str) and status.strip() else "started"
        resolved_elapsed = _preview_elapsed_ms(elapsed_ms)
        return _with_call_id_preview(
            f"Tool: {resolved_name} started status={resolved_status} elapsed={resolved_elapsed}",
            data=data,
        )

    if event_name == "tool_exec_running":
        name = data.get("name")
        status = data.get("status")
        elapsed_ms = data.get("elapsed_ms")
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        resolved_status = str(status) if isinstance(status, str) and status.strip() else "running"
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
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        resolved_stream = str(stream) if isinstance(stream, str) and stream.strip() else "<unknown>"
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
        resolved_name = str(name) if isinstance(name, str) and name.strip() else "<unknown>"
        resolved_status = str(status) if isinstance(status, str) and status.strip() else "<unknown>"
        resolved_duration = _preview_elapsed_ms(duration_ms)
        resolved_exit_code = str(exit_code) if isinstance(exit_code, int) else "<unknown>"
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
    resolved_status = str(status).strip().lower() if isinstance(status, str) and status.strip() else "<unknown>"
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


def _filter_previewed_tool_updates(*, tool_updates: list[str], previewed_tool_lines: set[str]) -> list[str]:
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


def _tool_preview_identity(*, event_name: str, data: dict[str, object], run_id: str) -> str | None:
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
