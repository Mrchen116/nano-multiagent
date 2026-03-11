"""Canonical hook logging facade and per-dispatch context container."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from agent.core.observability.logger import log_debug, log_error, log_info, log_warn
from agent.core.observability.tracing import current_trace_id

LogSink = Callable[[str, str, Mapping[str, Any]], None]


@dataclass(frozen=True, slots=True)
class HookModelCall:
    """Model call request shape exposed to hook handlers."""

    session_id: str
    system_prompt: str
    user_prompt: str
    model: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HookModelResult:
    """Model call result returned to hook handlers."""

    model: str
    content: str
    raw: Mapping[str, Any] = field(default_factory=dict)


HookModelCaller = Callable[[HookModelCall], HookModelResult]
HookSessionEventPublisher = Callable[[str, Mapping[str, Any]], None]


class HookLogger:
    """Emit structured hook logs with optional sink override and base fields."""

    def __init__(
        self,
        sink: LogSink | None = None,
        *,
        base_fields: Mapping[str, Any] | None = None,
    ) -> None:
        self._sink = sink
        self._base_fields = dict(base_fields or {})
        self._logger = logging.getLogger("agent.core.hooks")

    def debug(self, message: str, **fields: Any) -> None:
        """Emit a debug-level hook log entry."""

        self._emit("debug", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        """Emit an info-level hook log entry."""

        self._emit("info", message, fields)

    def warn(self, message: str, **fields: Any) -> None:
        """Emit a warning-level hook log entry."""

        self._emit("warning", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        """Emit an error-level hook log entry."""

        self._emit("error", message, fields)

    def with_fields(self, **fields: Any) -> "HookLogger":
        """Return a logger copy with merged base fields."""

        merged = dict(self._base_fields)
        for key, value in fields.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        return HookLogger(self._sink, base_fields=merged)

    def _emit(self, level: str, message: str, fields: Mapping[str, Any]) -> None:
        merged_fields = dict(self._base_fields)
        merged_fields.update(dict(fields))
        if self._sink is not None:
            self._sink(level, message, merged_fields)
            return
        if level == "debug":
            log_debug(message, **merged_fields)
            return
        if level == "info":
            log_info(message, **merged_fields)
            return
        if level == "warning":
            log_warn(message, **merged_fields)
            return
        if level == "error":
            log_error(message, **merged_fields)
            return
        if merged_fields:
            rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(merged_fields.items()))
            message = f"{message} | {rendered}"
        getattr(self._logger, level)(message)


@dataclass(frozen=True, slots=True)
class HookContext:
    """Carry immutable metadata and logger for a single hook dispatch."""

    session_id: str
    turn_id: str | None = None
    repo_root: Path | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    logger: HookLogger = field(default_factory=HookLogger)
    model_caller: HookModelCaller | None = None
    session_event_publisher: HookSessionEventPublisher | None = None

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id is required")
        if self.repo_root is not None:
            object.__setattr__(self, "repo_root", self.repo_root.expanduser().resolve())
        trace_id = self.metadata.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            trace_id = current_trace_id()
        tool_call_id = self.metadata.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            tool_call_id = None
        object.__setattr__(
            self,
            "logger",
            self.logger.with_fields(
                session_id=self.session_id,
                turn_id=self.turn_id,
                tool_call_id=tool_call_id,
                trace_id=trace_id,
            ),
        )

    def call_model(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HookModelResult:
        """Call the runtime model with enforced session-id consistency.

        Notes:
            The request session id is always `self.session_id`; callers cannot override it.
        """

        caller = self.model_caller
        if caller is None:
            raise RuntimeError("model caller is unavailable in this hook context")
        return caller(
            HookModelCall(
                session_id=self.session_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                metadata=dict(metadata or {}),
            )
        )

    def publish_session_event(
        self,
        *,
        event: str,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Publish one session-scoped event with enforced session consistency."""

        publisher = self.session_event_publisher
        if publisher is None:
            raise RuntimeError("session event publisher is unavailable in this hook context")
        publisher(event, dict(data or {}))
