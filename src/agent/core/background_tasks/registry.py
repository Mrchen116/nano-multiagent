"""Background task registry: state machine, terminal protection, stop handles."""

from __future__ import annotations

import threading
from dataclasses import replace
from typing import Any, Mapping

from agent.core.background_tasks.interfaces import (
    BackgroundSubagentMessageHandle,
    BackgroundTaskStopper,
    BackgroundTaskStore,
    Clock,
)
from agent.core.background_tasks.models import (
    BackgroundTaskRecord,
    BackgroundTaskStatus,
    BackgroundTaskType,
)


class BackgroundTaskRegistry:
    """In-memory state machine for background tasks.

    Terminal transitions are idempotent no-ops: once a record reaches a terminal
    state, subsequent ``complete`` / ``fail`` / ``kill`` calls are silently ignored.
    This prevents races between ``task_stop`` and runner completion callbacks.
    All mutations return a new ``BackgroundTaskRecord`` via ``replace()``.
    """

    def __init__(
        self,
        *,
        store: BackgroundTaskStore | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._lock = threading.Lock()
        self._records: dict[str, BackgroundTaskRecord] = {}
        self._stop_handles: dict[str, BackgroundTaskStopper] = {}
        self._message_handles: dict[str, BackgroundSubagentMessageHandle] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_subagent(
        self,
        *,
        task_id: str,
        parent_session_id: str,
        agent_id: str,
        agent_session_id: str,
        description: str,
        prompt: str | None,
        agent_type: str | None,
        output_file: str,
        workspace_root: str | None = None,
    ) -> BackgroundTaskRecord:
        record = BackgroundTaskRecord(
            task_id=task_id,
            task_type=BackgroundTaskType.SUBAGENT,
            parent_session_id=parent_session_id,
            agent_id=agent_id,
            agent_session_id=agent_session_id,
            description=description,
            prompt=prompt,
            agent_type=agent_type,
            output_file=output_file,
            status=BackgroundTaskStatus.QUEUED,
            created_at=self._now_iso(),
            workspace_root=workspace_root,
        )
        with self._lock:
            self._records[task_id] = record
        self._persist(record)
        return record

    def register_bash(
        self,
        *,
        task_id: str,
        parent_session_id: str,
        description: str,
        command: str,
        output_file: str,
        workspace_root: str | None = None,
    ) -> BackgroundTaskRecord:
        record = BackgroundTaskRecord(
            task_id=task_id,
            task_type=BackgroundTaskType.BASH,
            parent_session_id=parent_session_id,
            description=description,
            command=command,
            output_file=output_file,
            status=BackgroundTaskStatus.QUEUED,
            created_at=self._now_iso(),
            workspace_root=workspace_root,
        )
        with self._lock:
            self._records[task_id] = record
        self._persist(record)
        return record

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def mark_running(self, task_id: str) -> BackgroundTaskRecord:
        with self._lock:
            old = self._records[task_id]
            if self._guard_terminal(old):
                return old
            new = replace(
                old, status=BackgroundTaskStatus.RUNNING, started_at=self._now_iso()
            )
            self._records[task_id] = new
        self._persist(new)
        return new

    def complete(
        self,
        task_id: str,
        *,
        result_text: str | None = None,
        usage: Mapping[str, Any] | None = None,
        duration_ms: int | None = None,
        tool_use_count: int | None = None,
        notified: bool = False,
    ) -> BackgroundTaskRecord:
        with self._lock:
            old = self._records[task_id]
            if self._guard_terminal(old):
                return old
            new = replace(
                old,
                status=BackgroundTaskStatus.COMPLETED,
                ended_at=self._now_iso(),
                result_text=result_text,
                usage=usage,
                duration_ms=duration_ms,
                tool_use_count=tool_use_count,
                notified=notified,
            )
            self._records[task_id] = new
            self._clear_live_handles_locked(task_id)
        self._persist(new)
        return new

    def fail(self, task_id: str, *, error: str) -> BackgroundTaskRecord:
        with self._lock:
            old = self._records[task_id]
            if self._guard_terminal(old):
                return old
            new = replace(
                old,
                status=BackgroundTaskStatus.FAILED,
                ended_at=self._now_iso(),
                error=error,
            )
            self._records[task_id] = new
            self._clear_live_handles_locked(task_id)
        self._persist(new)
        return new

    def kill(
        self,
        task_id: str,
        *,
        reason: str = "stopped",
        notified: bool = False,
        result_text: str | None = None,
    ) -> BackgroundTaskRecord:
        # bugfix-420: mirror complete()'s notified / result_text so the kill path
        # can both suppress a model-facing notification (bash: notified=True) and
        # carry a partial result (subagent: result_text=last assistant text).
        # _guard_terminal stays first → the "first terminal wins" idempotency
        # invariant holds: a late runner callback can't overwrite these.
        with self._lock:
            old = self._records[task_id]
            if self._guard_terminal(old):
                return old
            new = replace(
                old,
                status=BackgroundTaskStatus.KILLED,
                ended_at=self._now_iso(),
                error=reason,
                notified=notified,
                result_text=result_text,
            )
            self._records[task_id] = new
            self._clear_live_handles_locked(task_id)
        self._persist(new)
        return new

    def mark_notified(self, task_id: str) -> BackgroundTaskRecord:
        with self._lock:
            old = self._records[task_id]
            new = replace(old, notified=True)
            self._records[task_id] = new
        self._persist(new)
        return new

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get(self, task_id: str) -> BackgroundTaskRecord | None:
        with self._lock:
            return self._records.get(task_id)

    def list_non_terminal(self) -> list[BackgroundTaskRecord]:
        with self._lock:
            return [
                r for r in self._records.values() if r.status not in _TERMINAL_STATUSES
            ]

    # ------------------------------------------------------------------
    # Stop handles
    # ------------------------------------------------------------------
    def set_stop_handle(self, task_id: str, handle: BackgroundTaskStopper) -> bool:
        """Register a background task's stop handle (killpg via the runner stopper).

        bugfix-417-M7 (decision 12): foreground bash no longer registers here — its
        killpg handle lives in ForegroundExecutionRegistry. This registry now only
        holds genuine background tasks (run_in_background, and foreground commands
        after auto-background hand-off), so the former ``foreground`` flag and the
        ``_foreground_task_ids`` set are gone.
        """
        with self._lock:
            record = self._records.get(task_id)
            if record is None or self._guard_terminal(record):
                return False
            self._stop_handles[task_id] = handle
            return True

    def request_stop(self, task_id: str) -> bool:
        with self._lock:
            handle = self._stop_handles.get(task_id)
            record = self._records.get(task_id)
        if record is None:
            return False
        if record.status not in (
            BackgroundTaskStatus.QUEUED,
            BackgroundTaskStatus.RUNNING,
        ):
            return False
        if handle is not None:
            handle.stop()
        return True

    # ------------------------------------------------------------------
    # Live subagent follow-up delivery
    # ------------------------------------------------------------------
    def set_message_handle(
        self,
        task_id: str,
        handle: BackgroundSubagentMessageHandle,
    ) -> bool:
        """Register the live delivery handle for a running subagent."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None or self._guard_terminal(record):
                return False
            self._message_handles[task_id] = handle
            return True

    def send_agent_message(self, agent_id: str, prompt: str) -> bool:
        """Deliver a follow-up prompt to a running subagent's live controller.

        Returns:
            True if the live subagent run accepted the message for safe-point
            injection; False if no running subagent handle can currently accept
            the message.
        """
        with self._lock:
            record = self._records.get(agent_id)
            if (
                record is None
                or record.task_type != BackgroundTaskType.SUBAGENT
                or record.status != BackgroundTaskStatus.RUNNING
            ):
                return False
            handle = self._message_handles.get(record.task_id)
        if handle is None:
            return False
        return handle.send_message(prompt)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _guard_terminal(self, record: BackgroundTaskRecord) -> bool:
        """Return True if the record is already terminal (transition should be skipped)."""
        return record.status in _TERMINAL_STATUSES

    def _clear_live_handles_locked(self, task_id: str) -> None:
        self._stop_handles.pop(task_id, None)
        self._message_handles.pop(task_id, None)

    def _persist(self, record: BackgroundTaskRecord) -> None:
        if self._store is None:
            return
        if record.status == BackgroundTaskStatus.QUEUED:
            self._store.insert(record)
        else:
            self._store.update(record)

    def _now_iso(self) -> str:
        if self._clock is None:
            from datetime import UTC, datetime

            return datetime.now(UTC).isoformat()
        return self._clock.now_iso()


_TERMINAL_STATUSES = {
    BackgroundTaskStatus.COMPLETED,
    BackgroundTaskStatus.FAILED,
    BackgroundTaskStatus.KILLED,
}


class _StopHandle:
    """Minimal stop handle used by the registry until a real runner handle is set."""

    def __init__(self, *, stop_fn: "_StopFn | None" = None) -> None:
        self._stop_fn = stop_fn

    def stop(self) -> None:
        if self._stop_fn is not None:
            self._stop_fn()


_StopFn = "callable[[], None]"
