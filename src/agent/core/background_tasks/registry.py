"""Background task registry: state machine, terminal protection, stop handles."""

from __future__ import annotations

import threading
from dataclasses import replace
from typing import Any, Mapping

from agent.core.background_tasks.interfaces import BackgroundTaskStore, Clock
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
        self._stop_handles: dict[str, "_StopHandle"] = {}
        # task_ids whose stop handle belongs to a FOREGROUND (run-blocking) tool —
        # i.e. a tool whose to_thread holds up the active run until it returns
        # (foreground bash). Used by stop_foreground_for_session so /stop and
        # cancel reap only the in-flight foreground subprocess tree and leave
        # user-launched background tasks (run_background) running (bugfix-417-M5,
        # #114).
        self._foreground_task_ids: set[str] = set()
        self._pending_messages: dict[str, list[str]] = {}

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
        self._persist(new)
        return new

    def kill(self, task_id: str, *, reason: str = "stopped") -> BackgroundTaskRecord:
        with self._lock:
            old = self._records[task_id]
            if self._guard_terminal(old):
                return old
            new = replace(
                old,
                status=BackgroundTaskStatus.KILLED,
                ended_at=self._now_iso(),
                error=reason,
            )
            self._records[task_id] = new
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
    def set_stop_handle(
        self, task_id: str, handle: "_StopHandle", *, foreground: bool = False
    ) -> None:
        """Register a task's stop handle.

        ``foreground=True`` marks the handle as belonging to a run-blocking
        foreground tool (foreground bash) so ``stop_foreground_for_session`` can
        target it on /stop / cancel without touching detached background tasks
        (bugfix-417-M5, #114).
        """
        with self._lock:
            self._stop_handles[task_id] = handle
            if foreground:
                self._foreground_task_ids.add(task_id)
            else:
                self._foreground_task_ids.discard(task_id)

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

    def stop_foreground_for_session(self, session_id: str) -> bool:
        """Stop the in-flight FOREGROUND tool(s) of a session, killing the
        subprocess tree via the registered stop handle (killpg, M4-hardened).

        Targets only non-terminal tasks whose handle was registered with
        ``foreground=True`` and whose ``parent_session_id`` matches — so a /stop
        or cancel reaps the run-blocking foreground subprocess but leaves
        user-launched background tasks (run_background) running (bugfix-417-M5,
        decision 10 / #114).

        Returns:
            True if at least one foreground task was found and stopped, False
            otherwise (the caller uses this to decide whether an interrupt must
            additionally force-cancel the parked carrier Task).
        """
        with self._lock:
            targets = [
                (task_id, self._stop_handles.get(task_id))
                for task_id in self._foreground_task_ids
                if (record := self._records.get(task_id)) is not None
                and record.parent_session_id == session_id
                and record.status
                in (BackgroundTaskStatus.QUEUED, BackgroundTaskStatus.RUNNING)
            ]
        stopped_any = False
        for _task_id, handle in targets:
            if handle is not None:
                handle.stop()
                stopped_any = True
        return stopped_any

    # ------------------------------------------------------------------
    # Pending messages (agent continuation)
    # ------------------------------------------------------------------
    def enqueue_agent_message(self, agent_id: str, prompt: str) -> None:
        with self._lock:
            self._pending_messages.setdefault(agent_id, []).append(prompt)

    def drain_agent_messages(self, agent_id: str) -> tuple[str, ...]:
        with self._lock:
            queue = self._pending_messages.pop(agent_id, [])
            return tuple(queue)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _guard_terminal(self, record: BackgroundTaskRecord) -> bool:
        """Return True if the record is already terminal (transition should be skipped)."""
        return record.status in _TERMINAL_STATUSES

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
