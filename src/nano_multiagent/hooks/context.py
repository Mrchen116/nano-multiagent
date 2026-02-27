import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


LogSink = Callable[[str, str, Mapping[str, Any]], None]


class HookLogger:
    def __init__(self, sink: LogSink | None = None) -> None:
        self._sink = sink
        self._logger = logging.getLogger("nano_multiagent.hooks")

    def debug(self, message: str, **fields: Any) -> None:
        self._emit("debug", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit("info", message, fields)

    def warn(self, message: str, **fields: Any) -> None:
        self._emit("warning", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit("error", message, fields)

    def _emit(self, level: str, message: str, fields: Mapping[str, Any]) -> None:
        if self._sink is not None:
            self._sink(level, message, dict(fields))
            return
        if fields:
            rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
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

