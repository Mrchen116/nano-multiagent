"""Protocols for background task adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

from agent.core.background_tasks.models import BackgroundTaskRecord


class Clock(Protocol):
    """Injected time source so core stays testable without real wall clock."""

    def now_iso(self) -> str: ...
    def now_ms(self) -> int: ...


class BackgroundTaskStore(Protocol):
    """Persistence protocol for terminal task metadata."""

    def insert(self, record: BackgroundTaskRecord) -> None: ...
    def update(self, record: BackgroundTaskRecord) -> None: ...
    def get(self, task_id: str) -> BackgroundTaskRecord | None: ...
    def list_non_terminal(self) -> Sequence[BackgroundTaskRecord]: ...


class BackgroundTaskOutput(Protocol):
    """File-based output protocol for bash background tasks."""

    def open(self, parent_session_id: str, task_id: str) -> Path: ...
    def append(self, task_id: str, text: str, *, stream: Literal["stdout", "stderr"]) -> None: ...
    def flush(self, task_id: str) -> None: ...


class BackgroundTaskStopper(Protocol):
    """Handle returned when a task is registered, used to request stop."""

    def stop(self) -> None: ...


class BackgroundSubagentRunner(Protocol):
    """Execute a subagent turn and report completion via callback."""

    def start(
        self,
        *,
        agent_session_id: str,
        parent_session_id: str,
        prompt: str,
        on_complete: "TaskCompletionCallback",
        on_fail: "TaskFailureCallback",
        workspace_root: Path | None = None,
    ) -> BackgroundTaskStopper: ...


class BackgroundBashRunner(Protocol):
    """Execute a shell command in the background and stream output."""

    def start(
        self,
        *,
        command: str,
        cwd: Path,
        output: BackgroundTaskOutput,
        task_id: str,
        timeout: float | None,
        on_complete: "TaskCompletionCallback",
        on_fail: "TaskFailureCallback",
    ) -> BackgroundTaskStopper: ...


class TaskCompletionCallback(Protocol):
    def __call__(
        self,
        *,
        task_id: str,
        result_text: str | None,
        usage: Mapping[str, Any] | None,
        duration_ms: int,
        tool_use_count: int,
    ) -> None: ...


class TaskFailureCallback(Protocol):
    def __call__(self, *, task_id: str, error: str) -> None: ...
