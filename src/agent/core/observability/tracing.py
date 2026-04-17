"""Request/run correlation context propagation and distributed tracing primitives."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Protocol, runtime_checkable

_CORRELATION_FIELDS = ("session_id", "turn_id", "tool_call_id", "trace_id")

_span_stack: ContextVar[list[Span]] = ContextVar("agent_span_stack", default=[])

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


# ---------------------------------------------------------------------------
# Tracing protocol and global tracer
# ---------------------------------------------------------------------------

@runtime_checkable
class Span(Protocol):
    """Mutable span handle used to annotate an in-flight operation."""

    def set_attribute(self, key: str, value: Any) -> None:
        ...

    def record_exception(self, exc: BaseException) -> None:
        ...

    def end(self) -> None:
        ...


@runtime_checkable
class Tracer(Protocol):
    """Provider-agnostic tracer used by core agent code."""

    def start_span(self, name: str, context: dict[str, Any] | None = None) -> Span:
        ...


class NoOpSpan:
    """Zero-overhead span used when no tracer is configured."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def end(self) -> None:
        pass


class NoOpTracer:
    """Zero-overhead tracer returned by default."""

    def start_span(self, name: str, context: dict[str, Any] | None = None) -> Span:
        return NoOpSpan()


_global_tracer: Tracer = NoOpTracer()


def set_tracer(tracer: Tracer) -> None:
    """Replace the process-global tracer."""
    global _global_tracer
    _global_tracer = tracer


def get_tracer() -> Tracer:
    """Return the current process-global tracer."""
    return _global_tracer


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Span]:
    """Convenience context manager for the global tracer."""
    stack = _span_stack.get()
    parent = stack[-1] if stack else None
    context: dict[str, Any] | None = {"parent": parent} if parent else None
    sp = _global_tracer.start_span(name, context=context)
    new_stack = list(stack)
    new_stack.append(sp)
    token = _span_stack.set(new_stack)
    for k, v in attrs.items():
        sp.set_attribute(k, v)
    try:
        yield sp
    except Exception as exc:
        sp.record_exception(exc)
        raise
    finally:
        sp.end()
        _span_stack.reset(token)
