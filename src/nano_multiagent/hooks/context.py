import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from nano_multiagent.observability.logger import log_debug, log_error, log_info, log_warn
from nano_multiagent.observability.tracing import current_trace_id


LogSink = Callable[[str, str, Mapping[str, Any]], None]


class HookLogger:
    def __init__(
        self,
        sink: LogSink | None = None,
        *,
        base_fields: Mapping[str, Any] | None = None,
    ) -> None:
        self._sink = sink
        self._base_fields = dict(base_fields or {})
        self._logger = logging.getLogger("nano_multiagent.hooks")

    def debug(self, message: str, **fields: Any) -> None:
        self._emit("debug", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit("info", message, fields)

    def warn(self, message: str, **fields: Any) -> None:
        self._emit("warning", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit("error", message, fields)

    def with_fields(self, **fields: Any) -> "HookLogger":
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
    session_id: str
    turn_id: str | None = None
    repo_root: Path | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    logger: HookLogger = field(default_factory=HookLogger)

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
