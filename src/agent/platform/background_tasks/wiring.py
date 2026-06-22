"""Assembly: registry + store + output + runners + clock."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Coroutine

from agent.core.agent.runtime import AgentRuntime
from agent.core.background_tasks.interfaces import (
    BackgroundBashRunner,
    BackgroundSubagentRunner,
    BackgroundTaskOutput,
    BackgroundTaskStore,
    Clock,
)
from agent.core.background_tasks.foreground_registry import ForegroundExecutionRegistry
from agent.core.background_tasks.models import BackgroundTaskRecord
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.runs.origin import RunOrigin
from agent.core.runs.registry import RunsRegistry

from .file_output import BashFileOutput
from .runtime_runner import RuntimeRunner
from .shell_runner import ShellRunner
from .task_store import InMemoryTaskStore


@dataclass(frozen=True, slots=True)
class BackgroundTaskWiring:
    """Holds all wired background-task components for injection into tools."""

    registry: BackgroundTaskRegistry
    foreground_registry: ForegroundExecutionRegistry
    store: BackgroundTaskStore
    output: BackgroundTaskOutput
    bash_runner: BackgroundBashRunner
    subagent_runner: BackgroundSubagentRunner
    clock: Clock


def wire_background_tasks(
    *,
    workspace_root: Path,
    runtime: AgentRuntime | None = None,
    runs_registry: RunsRegistry | None = None,
    manifest_path: Path | None = None,
    safety: Any | None = None,
) -> BackgroundTaskWiring:
    """Assemble and return all background-task platform adapters.

    Args:
        workspace_root: Root directory for bash task output files.
        runtime: AgentRuntime instance for subagent runner.
        runs_registry: RunsRegistry for completion notification delivery.
        manifest_path: Optional path for task manifest JSONL append.
        safety: Optional ToolSafety instance for command policy enforcement.
    """
    clock = _SystemClock()
    store = InMemoryTaskStore(manifest_path=manifest_path)
    output = BashFileOutput(workspace_root=workspace_root)
    bash_runner = ShellRunner(safety=safety)
    subagent_runner = (
        RuntimeRunner(
            runtime=runtime,
            event_loop=runs_registry.get_event_loop()
            if runs_registry is not None
            else None,
        )
        if runtime is not None
        else _NoOpSubagentRunner()
    )

    registry = BackgroundTaskRegistry(store=store, clock=clock)
    # bugfix-417-M7 (decision 12): foreground bash registers its killpg stopper here,
    # not in BackgroundTaskRegistry — so it never becomes a background task and never
    # emits a <task-notification>. The kernel injects foreground_registry.stop_for_session
    # into RunsRegistry as the foreground stopper port.
    foreground_registry = ForegroundExecutionRegistry()

    # Wire notification delivery if RunsRegistry is available.
    if runs_registry is not None:
        _wire_notification_callbacks(registry, runs_registry)

    return BackgroundTaskWiring(
        registry=registry,
        foreground_registry=foreground_registry,
        store=store,
        output=output,
        bash_runner=bash_runner,
        subagent_runner=subagent_runner,
        clock=clock,
    )


def _wire_notification_callbacks(
    registry: BackgroundTaskRegistry,
    runs_registry: RunsRegistry,
) -> None:
    """Inject a store wrapper that delivers notifications on terminal transitions.

    This replaces the raw store with a forwarding wrapper so that
    registry mutations automatically trigger parent-session wake-up.
    """
    raw_store = registry._store  # type: ignore[attr-defined]
    if raw_store is None:
        return

    # Extract session_manager once at wire time so _deliver_notification does not
    # need to poke the private attribute at each call (testability + avoids coupling).
    # bugfix-404 F3: use the public property instead of reflecting on _session_manager.
    session_manager = runs_registry.session_manager

    class _NotifyingStore:
        def __init__(self, delegate: BackgroundTaskStore) -> None:
            self._delegate = delegate

        def insert(self, record: BackgroundTaskRecord) -> None:
            self._delegate.insert(record)

        def update(self, record: BackgroundTaskRecord) -> None:
            self._delegate.update(record)
            if (
                record.status in {"completed", "failed", "killed"}
                and not record.notified
            ):
                _deliver_notification(record, runs_registry, session_manager)

        def get(self, task_id: str) -> BackgroundTaskRecord | None:
            return self._delegate.get(task_id)

        def list_non_terminal(self) -> Any:
            return self._delegate.list_non_terminal()

    registry._store = _NotifyingStore(raw_store)  # type: ignore[attr-defined]


def _deliver_notification(
    record: BackgroundTaskRecord,
    runs_registry: RunsRegistry,
    session_manager: Any = None,
) -> None:
    """Deliver a <task-notification> to the parent session.

    Skips silently for subagent parent sessions (kind="subagent" in metadata),
    because those sessions are not managed by the top-level RunsRegistry.
    Any other submit failure is logged rather than swallowed.
    """
    from agent.core.background_tasks.notifications import build_task_notification_xml
    from agent.core.llm.interfaces import LLMMessage
    from agent.core.observability.logger import log_debug, log_error

    parent = record.parent_session_id
    notification_xml = build_task_notification_xml(record)

    active_run_id = runs_registry.get_active_run_id(parent)
    if active_run_id is not None:
        injected = runs_registry.inject_pending_message(
            parent,
            LLMMessage(role="user", content=notification_xml),
        )
        if injected:
            return

    # Parent idle: check whether this is a subagent session before submitting.
    # Subagent sessions (kind="subagent") are not registered in the top-level
    # RunsRegistry; submitting to them would always fail, so skip with a debug log.
    workspace_root = (
        Path(record.workspace_root) if record.workspace_root is not None else None
    )
    if session_manager is not None:
        parent_session = session_manager.get_session(
            parent, workspace_root=workspace_root
        )
        if (
            parent_session is not None
            and parent_session.metadata.get("kind") == "subagent"
        ):
            log_debug(
                "background_task_notify_skip_subagent_parent",
                task_id=record.task_id,
                parent_session_id=parent,
            )
            return

    try:
        runs_registry.submit(
            session_id=parent,
            parts=[{"type": "text", "text": notification_xml}],
            origin=RunOrigin.BACKGROUND_TASK,
            source_task_id=record.task_id,
            workspace_root=workspace_root,
        )
    except Exception as exc:  # noqa: BLE001
        log_error(
            "background_task_notify_delivery_failed",
            task_id=record.task_id,
            parent_session_id=parent,
            workspace_root=str(workspace_root),
            error=str(exc),
        )


class _SystemClock:
    def now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def now_ms(self) -> int:
        return int(datetime.now(UTC).timestamp() * 1000)


class _NoOpSubagentRunner(BackgroundSubagentRunner):
    """Placeholder when no AgentRuntime is available (e.g. unit tests)."""

    def start(
        self,
        *,
        agent_session_id: str,
        parent_session_id: str,
        prompt: str,
        on_complete: TaskCompletionCallback,
        on_fail: TaskFailureCallback,
        on_kill: TaskKillCallback,
        workspace_root: "Path | None" = None,
        llm_session_id: str | None = None,
    ) -> BackgroundTaskStopper:
        on_fail(task_id=agent_session_id, error="subagent runner is not configured")
        return _NoOpStopper()

    def submit_foreground(self, coro: "Coroutine[Any, Any, Any]") -> "Future":
        coro.close()
        future: "Future" = Future()
        future.set_exception(RuntimeError("subagent runner is not configured"))
        return future


class _NoOpStopper:
    def stop(self) -> None:
        pass
