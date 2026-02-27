from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Any, Callable, Iterator

from .tracing import current_correlation

LogSink = Callable[[str, str, dict[str, Any]], None]

_REQUIRED_CORRELATION_FIELDS = ("session_id", "turn_id", "tool_call_id", "trace_id")
_logger = logging.getLogger("nano_multiagent.observability")
_sink_lock = Lock()
_sink: LogSink | None = None


@contextmanager
def capture_logs() -> Iterator[list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []

    def _capture(level: str, message: str, fields: dict[str, Any]) -> None:
        records.append(
            {
                "level": level,
                "message": message,
                "fields": dict(fields),
            }
        )

    previous = _set_sink(_capture)
    try:
        yield records
    finally:
        _set_sink(previous)


def log_debug(message: str, **fields: Any) -> None:
    _emit("debug", message, fields)


def log_info(message: str, **fields: Any) -> None:
    _emit("info", message, fields)


def log_warn(message: str, **fields: Any) -> None:
    _emit("warning", message, fields)


def log_error(message: str, **fields: Any) -> None:
    _emit("error", message, fields)


def _emit(level: str, message: str, fields: dict[str, Any]) -> None:
    merged_fields: dict[str, Any] = current_correlation()
    merged_fields.update(fields)
    for key in _REQUIRED_CORRELATION_FIELDS:
        merged_fields.setdefault(key, None)

    active_sink = _get_sink()
    if active_sink is not None:
        active_sink(level, message, merged_fields)
        return

    if merged_fields:
        rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(merged_fields.items()))
        message = f"{message} | {rendered}"
    getattr(_logger, level)(message)


def _get_sink() -> LogSink | None:
    with _sink_lock:
        return _sink


def _set_sink(next_sink: LogSink | None) -> LogSink | None:
    global _sink
    with _sink_lock:
        previous = _sink
        _sink = next_sink
        return previous
