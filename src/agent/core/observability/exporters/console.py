"""Console tracer that prints slow-request waterfall spans with thresholds."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any

from agent.core.observability.tracing import Span, Tracer


@dataclass
class ConsoleSpan(Span):
    """Mutable span handle that accumulates attributes and prints on end."""

    name: str
    start_time: float
    threshold_ms: float
    parent: ConsoleSpan | None = None
    children: list[ConsoleSpan] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    _ended: bool = field(default=False, repr=False)
    _exception: BaseException | None = field(default=None, repr=False)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self._exception = exc

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        if self.parent is not None:
            self.parent.children.append(self)
            return
        if duration_ms < self.threshold_ms and not any(
            child._should_print() for child in self.children
        ):
            return
        self._print_waterfall(indent=0, duration_ms=duration_ms)

    def _should_print(self) -> bool:
        if not self._ended:
            return False
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        return duration_ms >= self.threshold_ms or any(
            child._should_print() for child in self.children
        )

    def _print_waterfall(self, *, indent: int, duration_ms: float) -> None:
        prefix = "  " * indent
        exc_flag = " [ERR]" if self._exception is not None else ""
        attr_str = ""
        if self.attributes:
            attr_str = " | " + ", ".join(f"{k}={v}" for k, v in self.attributes.items())
        sys.stderr.write(
            f"{prefix}[{duration_ms:6.1f}ms] {self.name}{exc_flag}{attr_str}\n"
        )
        for child in self.children:
            child_dur = (time.perf_counter() - child.start_time) * 1000
            child._print_waterfall(indent=indent + 1, duration_ms=child_dur)


@dataclass
class ConsoleTracer(Tracer):
    """Tracer that prints span waterfalls to stderr when thresholds are exceeded."""

    threshold_ms: float = 100.0

    def start_span(
        self,
        name: str,
        context: dict[str, Any] | None = None,
    ) -> Span:
        parent = None
        if context is not None:
            raw_parent = context.get("parent")
            if isinstance(raw_parent, ConsoleSpan):
                parent = raw_parent
        return ConsoleSpan(
            name=name,
            start_time=time.perf_counter(),
            threshold_ms=self.threshold_ms,
            parent=parent,
        )
