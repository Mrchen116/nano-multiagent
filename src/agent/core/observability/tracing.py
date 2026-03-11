"""Request/run correlation context propagation for logs and diagnostics."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_CORRELATION_FIELDS = ("session_id", "turn_id", "tool_call_id", "trace_id")

_UNSET = object()
_context: ContextVar[dict[str, str | None]] = ContextVar(
    "agent_observability_context",
    default={
        "session_id": None,
        "turn_id": None,
        "tool_call_id": None,
        "trace_id": None,
    },
)


@contextmanager
def bind_correlation(
    *,
    session_id: str | None | object = _UNSET,
    turn_id: str | None | object = _UNSET,
    tool_call_id: str | None | object = _UNSET,
    trace_id: str | None | object = _UNSET,
) -> Iterator[None]:
    """Bind correlation fields for current context and restore on exit."""
    current = dict(_context.get())
    if session_id is not _UNSET:
        current["session_id"] = _string_or_none(session_id)
    if turn_id is not _UNSET:
        current["turn_id"] = _string_or_none(turn_id)
    if tool_call_id is not _UNSET:
        current["tool_call_id"] = _string_or_none(tool_call_id)
    if trace_id is not _UNSET:
        current["trace_id"] = _string_or_none(trace_id)

    token = _context.set(current)
    try:
        yield
    finally:
        _context.reset(token)


def current_correlation() -> dict[str, str | None]:
    """Return normalized correlation dictionary with all known keys present."""
    current = dict(_context.get())
    for field in _CORRELATION_FIELDS:
        current.setdefault(field, None)
    return current


def current_trace_id() -> str | None:
    """Return active trace id when present and non-empty."""
    trace_id = current_correlation().get("trace_id")
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    return None


def _string_or_none(value: str | None | object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return str(value)
