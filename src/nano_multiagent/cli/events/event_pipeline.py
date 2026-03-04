"""Semantic pipeline helpers for REPL async event processing."""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

_REPLAY_FALLBACK_DEDUPE_EVENTS = {
    "run_status",
    "tool_start",
    "tool_end",
    "tool_exec_started",
    "tool_exec_running",
    "tool_exec_chunk",
    "tool_exec_exit",
}


@dataclass(frozen=True)
class NormalizedSessionEvent:
    """Normalized event shape consumed by the CLI event pipeline."""

    event_id: str
    event_name: str
    data: dict[str, object]


@dataclass(frozen=True)
class ReplViewModel:
    """Structured turn summary view produced from consumed semantic events."""

    status_updates: list[str]
    tool_updates: list[str]


class EventDedupeWindow:
    """Bounded dedupe window for event ids and semantic fallback keys."""

    def __init__(
        self,
        *,
        max_event_ids: int = 2048,
        max_runs: int = 32,
        max_fallback_keys_per_run: int = 1024,
    ) -> None:
        self._max_event_ids = max(1, max_event_ids)
        self._max_runs = max(1, max_runs)
        self._max_fallback_keys_per_run = max(1, max_fallback_keys_per_run)
        self._event_ids: OrderedDict[str, None] = OrderedDict()
        self._fallback_by_run: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()

    def has_event_id(self, event_id: str) -> bool:
        """Check whether event id has appeared in the window."""
        return event_id in self._event_ids

    def record_event_id(self, event_id: str) -> None:
        """Record event id with bounded LRU eviction."""
        if event_id in self._event_ids:
            self._event_ids.move_to_end(event_id)
            return
        self._event_ids[event_id] = None
        while len(self._event_ids) > self._max_event_ids:
            self._event_ids.popitem(last=False)

    def has_fallback_key(self, *, run_id: str, key: str) -> bool:
        """Check whether semantic fallback key has appeared in run bucket."""
        bucket = self._fallback_by_run.get(run_id)
        if bucket is None:
            return False
        return key in bucket

    def record_fallback_key(self, *, run_id: str, key: str) -> None:
        """Record semantic fallback key with per-run and global bounds."""
        bucket = self._fallback_by_run.get(run_id)
        if bucket is None:
            bucket = OrderedDict()
            self._fallback_by_run[run_id] = bucket
        else:
            self._fallback_by_run.move_to_end(run_id)
        if key in bucket:
            bucket.move_to_end(key)
        else:
            bucket[key] = None
        while len(bucket) > self._max_fallback_keys_per_run:
            bucket.popitem(last=False)
        while len(self._fallback_by_run) > self._max_runs:
            self._fallback_by_run.popitem(last=False)


def normalize_session_event(event: object) -> NormalizedSessionEvent:
    """Normalize raw SSE event payload into stable internal shape."""
    if not isinstance(event, dict):
        return NormalizedSessionEvent(event_id="", event_name="message", data={})
    event_id = event.get("event_id")
    event_name = event.get("event")
    data = event.get("data")
    resolved_id = event_id.strip() if isinstance(event_id, str) else ""
    resolved_name = event_name.strip() if isinstance(event_name, str) and event_name.strip() else "message"
    resolved_data = data if isinstance(data, dict) else {}
    return NormalizedSessionEvent(event_id=resolved_id, event_name=resolved_name, data=resolved_data)


def consume_event_for_run(
    *,
    normalized_event: NormalizedSessionEvent,
    run_id: str,
    dedupe_window: EventDedupeWindow,
    seen_event_ids: set[str] | None = None,
    seen_event_fingerprints: set[str] | None = None,
) -> bool:
    """Return whether normalized event should be consumed for the target run."""
    data = normalized_event.data
    if data.get("run_id") != run_id:
        return False

    event_id = normalized_event.event_id
    if event_id:
        if (seen_event_ids is not None and event_id in seen_event_ids) or dedupe_window.has_event_id(event_id):
            return False
        dedupe_window.record_event_id(event_id)
        if seen_event_ids is not None:
            seen_event_ids.add(event_id)

    replay_key = replay_fallback_dedupe_key(event_name=normalized_event.event_name, data=data)
    if replay_key is not None:
        if (
            seen_event_fingerprints is not None
            and replay_key in seen_event_fingerprints
        ) or dedupe_window.has_fallback_key(run_id=run_id, key=replay_key):
            return False
        dedupe_window.record_fallback_key(run_id=run_id, key=replay_key)
        if seen_event_fingerprints is not None:
            seen_event_fingerprints.add(replay_key)

    return True


def replay_fallback_dedupe_key(*, event_name: str, data: dict[str, object]) -> str | None:
    """Build semantic fallback dedupe key for missing/unreliable event ids."""
    if event_name not in _REPLAY_FALLBACK_DEDUPE_EVENTS:
        return None
    semantic_payload: dict[str, object] = {
        "event": event_name,
        "run_id": _read_str(data.get("run_id")) or "<unknown-run>",
    }

    if event_name == "run_status":
        semantic_payload["status"] = _read_str(data.get("status")) or "<unknown-status>"
        attempt = data.get("attempt")
        if isinstance(attempt, int):
            semantic_payload["attempt"] = attempt
        next_delay = data.get("next_delay")
        if isinstance(next_delay, (int, float)):
            semantic_payload["next_delay"] = float(next_delay)
        cooldown = data.get("cooldown")
        if isinstance(cooldown, (int, float)):
            semantic_payload["cooldown"] = float(cooldown)
        last_error = data.get("last_error")
        if isinstance(last_error, dict):
            semantic_payload["last_error"] = {
                "code": _read_str(last_error.get("code")),
                "message": _read_str(last_error.get("message")),
            }
        return _stable_key(semantic_payload)

    semantic_payload["name"] = _read_str(data.get("name")) or "<unknown-tool>"
    semantic_payload["call_id"] = _read_str(data.get("call_id")) or "<missing-call-id>"

    if event_name == "tool_start":
        semantic_payload["arguments"] = data.get("arguments")
    elif event_name == "tool_end":
        semantic_payload["output"] = data.get("output")
        semantic_payload["error"] = data.get("error")
    elif event_name in {"tool_exec_started", "tool_exec_running"}:
        semantic_payload["status"] = _read_str(data.get("status")) or "<unknown-status>"
        elapsed_ms = data.get("elapsed_ms")
        if isinstance(elapsed_ms, (int, float)):
            semantic_payload["elapsed_ms"] = int(elapsed_ms)
    elif event_name == "tool_exec_chunk":
        semantic_payload["stream"] = _read_str(data.get("stream")) or "<unknown-stream>"
        seq = data.get("seq")
        if isinstance(seq, int):
            semantic_payload["seq"] = seq
        semantic_payload["chunk"] = data.get("chunk")
    elif event_name == "tool_exec_exit":
        semantic_payload["status"] = _read_str(data.get("status")) or "<unknown-status>"
        duration_ms = data.get("duration_ms")
        if isinstance(duration_ms, (int, float)):
            semantic_payload["duration_ms"] = int(duration_ms)
        exit_code = data.get("exit_code")
        if isinstance(exit_code, int):
            semantic_payload["exit_code"] = exit_code

    return _stable_key(semantic_payload)


def build_repl_view_model(
    *,
    events: list[tuple[str, dict[str, object]]],
    preview_line_resolver: Callable[[str, dict[str, object]], str | None],
    status_line_resolver: Callable[[dict[str, object]], str] | None = None,
) -> ReplViewModel:
    """Build compact REPL summary model from semantic event stream."""
    status_updates: list[str] = []
    tool_order: list[str] = []
    tool_views: dict[str, dict[str, object]] = {}

    def _ensure_tool(group_key: str, *, tool_name: str) -> dict[str, object]:
        if group_key not in tool_views:
            tool_views[group_key] = {"tool_name": tool_name}
            tool_order.append(group_key)
        return tool_views[group_key]

    for event_name, data in events:
        if event_name == "run_status":
            if status_line_resolver is None:
                status_line = _format_status_progress(data)
            else:
                status_line = status_line_resolver(data)
            if status_line:
                status_updates.append(status_line)
            continue
        if event_name not in {
            "tool_start",
            "tool_end",
            "tool_exec_started",
            "tool_exec_running",
            "tool_exec_chunk",
            "tool_exec_exit",
        }:
            continue
        group_key = _tool_group_key(data)
        tool_name = _tool_name_from_data(data)
        if not group_key or not tool_name:
            continue
        tool_line = preview_line_resolver(event_name, data)
        if not tool_line:
            continue
        slot = _ensure_tool(group_key, tool_name=tool_name)
        if event_name == "tool_start":
            slot["start"] = tool_line
            continue
        if event_name == "tool_end":
            if " error=" in tool_line:
                slot["error"] = tool_line
            else:
                slot["output"] = tool_line
            continue
        if event_name == "tool_exec_started":
            slot["exec_started"] = tool_line
            continue
        if event_name == "tool_exec_chunk":
            _record_chunk_count(slot, stream=data.get("stream"))
            continue
        if event_name == "tool_exec_exit":
            slot["exec_exit"] = tool_line

    tool_updates: list[str] = []
    for group_key in tool_order:
        slot = tool_views.get(group_key, {})
        if not slot:
            continue
        progress_line = _format_tool_chunk_progress(slot)
        error_line = slot.get("error")
        if isinstance(error_line, str) and error_line:
            start_line = slot.get("start")
            if isinstance(start_line, str) and start_line:
                tool_updates.append(start_line)
            if progress_line:
                tool_updates.append(progress_line)
            tool_updates.append(error_line)
            continue

        output_line = slot.get("output")
        exit_line = slot.get("exec_exit")
        started_line = slot.get("exec_started")

        if isinstance(output_line, str) and output_line and not isinstance(exit_line, str):
            tool_updates.append(output_line)
        if progress_line:
            tool_updates.append(progress_line)
        if isinstance(exit_line, str) and exit_line:
            tool_updates.append(exit_line)
            continue
        if isinstance(started_line, str) and started_line and not isinstance(output_line, str):
            tool_updates.append(started_line)
            continue
    return ReplViewModel(status_updates=status_updates, tool_updates=tool_updates)


def _record_chunk_count(slot: dict[str, object], *, stream: object) -> None:
    if isinstance(stream, str) and stream.strip():
        stream_key = stream.strip().lower()
        count_key = f"chunk_count_{stream_key}"
        current_count = slot.get(count_key)
        slot[count_key] = current_count + 1 if isinstance(current_count, int) else 1
        return
    current_count = slot.get("chunk_count_unknown")
    slot["chunk_count_unknown"] = current_count + 1 if isinstance(current_count, int) else 1


def _format_tool_chunk_progress(slot: dict[str, object]) -> str | None:
    tool_name = slot.get("tool_name")
    resolved_name = str(tool_name) if isinstance(tool_name, str) and tool_name.strip() else "<unknown>"
    count_items: list[tuple[str, int]] = []
    for key, label in (
        ("chunk_count_stdout", "stdout"),
        ("chunk_count_stderr", "stderr"),
        ("chunk_count_unknown", "unknown"),
    ):
        raw = slot.get(key)
        if isinstance(raw, int) and raw > 0:
            count_items.append((label, raw))
    if not count_items:
        return None
    total_chunks = sum(count for _, count in count_items)
    details = ", ".join(f"{label}={count}" for label, count in count_items)
    return f"Tool {resolved_name} progress chunks={total_chunks} ({details})"


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
        code = _read_str(last_error.get("code"))
        message = _read_str(last_error.get("message"))
        if code and message:
            parts.append(f"last error {code}: {message}")
        elif message:
            parts.append(f"last error {message}")
    return ", ".join(parts)


def _tool_name_from_data(data: dict[str, object]) -> str:
    raw = data.get("name")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _tool_group_key(data: dict[str, object]) -> str:
    name = _tool_name_from_data(data)
    if not name:
        return ""
    call_id = _read_str(data.get("call_id"))
    if call_id:
        return f"{name}::{call_id}"
    return name


def _read_str(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _stable_key(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
