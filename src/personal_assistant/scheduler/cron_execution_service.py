"""Unified cron execution service: scheduled and manual runs share one entry point.

bugfix-402 Decision 2: Gateway has exactly one CronExecutionService; both the scheduler
tick and the manual run tool call the same enqueue() method.

The service is responsible for:
- Validating job exists and is enabled (before creating any state)
- Persisting an "accepted" record to runs.jsonl
- Submitting, delivering, and finalizing accepted work through owned collaborators
- Tracking accepted→running→terminal state transitions in runs.jsonl

runs.jsonl lives at <workspace>/.nanoassistant/cron/runs.jsonl (append-only).
Each store owner replays it once, then maintains the latest per-request state
in memory while durably appending every transition.

On gateway restart, converge_stale_on_restart() marks any accepted/running records
as failed(gateway_restarted) so they never stay permanently "in progress".
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Protocol

import logging

from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore
from personal_assistant.gateway.runtime_delivery.stream import (
    StreamRunOutcome,
    stream_run_to_completion,
)
from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

_log = logging.getLogger(__name__)

_CRON_SUBDIR = ".nanoassistant/cron"
_RUNS_FILENAME = "runs.jsonl"

# Maximum number of terminal records to retain per job.
_MAX_TERMINAL_RECORDS_PER_JOB = 100
_TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CronRunRecord:
    """Single cron run lifecycle record.

    Each state transition is appended as a new line in runs.jsonl; the store
    materializes the final state per request_id by replaying the log.

    Args:
        request_id: Unique identifier for this enqueue request.
        job_id: Job that was enqueued.
        trigger: "scheduled" or "manual".
        status: Current lifecycle state.
        accepted_at: ISO timestamp when the request was accepted.
        started_at: ISO timestamp when kernel run started (optional).
        finished_at: ISO timestamp when the run reached a terminal state (optional).
        kernel_run_id: Kernel run ID assigned at submit time (optional).
        target_conversation_id: IM conversation the result was delivered to (optional).
        result_summary: Short text summary of the final assistant message (optional).
        error: Error dict with at least a "message" key (optional).
    """

    request_id: str
    job_id: str
    trigger: str
    status: str
    accepted_at: str
    started_at: str | None = None
    finished_at: str | None = None
    kernel_run_id: str | None = None
    target_conversation_id: str | None = None
    result_summary: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# CronRunsStore: append-only runs.jsonl persistence
# ---------------------------------------------------------------------------


class CronRunsStore:
    """Persist cron run lifecycle events to <workspace>/.nanoassistant/cron/runs.jsonl.

    Each entry in runs.jsonl is a JSON object with at minimum request_id, job_id,
    trigger, status, accepted_at.  Status transitions are appended as new lines;
    the store materializes the latest state per request_id when querying.

    list_by_job() returns the materialized records for a single job, sorted by
    accepted_at descending (newest first), capped at _MAX_TERMINAL_RECORDS_PER_JOB.

    converge_stale_on_restart() marks any accepted or running records as
    failed(gateway_restarted) — called once at Gateway startup to prevent
    permanently-pending records after a crash.

    Args:
        workspace_root: Agent workspace root directory.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._root = Path(workspace_root).expanduser().resolve()
        self._cron_dir = self._root / _CRON_SUBDIR
        self._runs_path = self._cron_dir / _RUNS_FILENAME
        self._lock = threading.RLock()
        self._materialized: dict[str, CronRunRecord] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, record: CronRunRecord) -> None:
        """Append one record and publish it to this owner's materialized state."""

        with self._lock:
            materialized = self._materialize_locked()
            self._ensure_dir()
            line = json.dumps(asdict(record), ensure_ascii=False)
            with self._runs_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            # Durable append is the transition commit point; readers only observe
            # the new state after the line has been written successfully.
            materialized[record.request_id] = record
            if record.status in _TERMINAL_RUN_STATUSES:
                self._prune_terminal_records_locked(
                    materialized,
                    job_id=record.job_id,
                )

    def update_status(
        self,
        request_id: str,
        status: str,
        *,
        started_at: str | None = None,
        finished_at: str | None = None,
        kernel_run_id: str | None = None,
        target_conversation_id: str | None = None,
        result_summary: str | None = None,
        error: str | None = None,
    ) -> None:
        """Append a status-update entry for an existing request_id."""
        with self._lock:
            existing = self._materialize_locked().get(request_id)
            if existing is None:
                _log.warning(
                    "cron runs: update_status for unknown request_id=%r (store may be inconsistent)",
                    request_id,
                )
                # Preserve the established append-only recovery behavior for an
                # unknown request while still publishing it to the in-memory state.
                partial = CronRunRecord(
                    request_id=request_id,
                    job_id="",
                    trigger="unknown",
                    status=status,
                    accepted_at=_utc_now(),
                    started_at=started_at,
                    finished_at=finished_at,
                    kernel_run_id=kernel_run_id,
                    error=error,
                )
                self.append(partial)
                return

            updated = CronRunRecord(
                request_id=request_id,
                job_id=existing.job_id,
                trigger=existing.trigger,
                status=status,
                accepted_at=existing.accepted_at,
                started_at=started_at or existing.started_at,
                finished_at=finished_at or existing.finished_at,
                kernel_run_id=kernel_run_id or existing.kernel_run_id,
                target_conversation_id=target_conversation_id
                or existing.target_conversation_id,
                result_summary=result_summary or existing.result_summary,
                error=error or existing.error,
            )
            self.append(updated)

    def list_by_job(
        self,
        job_id: str,
        *,
        limit: int = 20,
        max_limit: int = 100,
    ) -> list[CronRunRecord]:
        """Return materialized records for a job, sorted by accepted_at descending.

        Args:
            job_id: Job to query.
            limit: Maximum records to return (default 20).
            max_limit: Hard cap (default 100).

        Returns:
            List of CronRunRecord, newest first.
        """
        effective_limit = min(limit, max_limit)
        all_records = self._materialize_all()
        job_records = [r for r in all_records.values() if r.job_id == job_id]
        job_records.sort(key=lambda r: r.accepted_at, reverse=True)
        return job_records[:effective_limit]

    def converge_stale_on_restart(self) -> None:
        """Mark all non-terminal records as failed(gateway_restarted).

        Called once during Gateway startup (after CronExecutionService is created)
        so that records that were accepted or running before the crash are never
        permanently in progress.
        """
        with self._lock:
            stale = [
                record
                for record in self._materialize_locked().values()
                if record.status in ("accepted", "running")
            ]
            now = _utc_now()
            for rec in stale:
                self.update_status(
                    rec.request_id,
                    "failed",
                    finished_at=now,
                    error="gateway_restarted",
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self._cron_dir.mkdir(parents=True, exist_ok=True)

    def _materialize_all(self) -> dict[str, CronRunRecord]:
        """Return a snapshot after replaying runs.jsonl at most once per owner."""

        with self._lock:
            return dict(self._materialize_locked())

    def _materialize_locked(self) -> dict[str, CronRunRecord]:
        """Return the owned latest-state index while the caller holds ``_lock``."""

        if self._materialized is None:
            self._materialized = self._load_all()
        return self._materialized

    def _load_all(self) -> dict[str, CronRunRecord]:
        """Replay the durable log once for a newly-created store owner."""

        if not self._runs_path.exists():
            return {}
        records: dict[str, CronRunRecord] = {}
        try:
            raw = self._runs_path.read_text(encoding="utf-8")
        except OSError:
            return {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            request_id = data.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                continue
            records[request_id] = _record_from_dict(data)
        self._prune_terminal_records_locked(records)
        return records

    @staticmethod
    def _prune_terminal_records_locked(
        records: dict[str, CronRunRecord],
        *,
        job_id: str | None = None,
    ) -> None:
        """Bound terminal materialization while retaining every active record."""

        job_ids = (
            {job_id}
            if job_id is not None
            else {
                record.job_id
                for record in records.values()
                if record.status in _TERMINAL_RUN_STATUSES
            }
        )
        for current_job_id in job_ids:
            terminal = sorted(
                (
                    record
                    for record in records.values()
                    if record.job_id == current_job_id
                    and record.status in _TERMINAL_RUN_STATUSES
                ),
                key=lambda record: (record.accepted_at, record.request_id),
                reverse=True,
            )
            for expired in terminal[_MAX_TERMINAL_RECORDS_PER_JOB:]:
                records.pop(expired.request_id, None)


def _record_from_dict(d: dict[str, Any]) -> CronRunRecord:
    return CronRunRecord(
        request_id=str(d.get("request_id", "")),
        job_id=str(d.get("job_id", "")),
        trigger=str(d.get("trigger", "unknown")),
        status=str(d.get("status", "unknown")),
        accepted_at=str(d.get("accepted_at", "")),
        started_at=d.get("started_at"),
        finished_at=d.get("finished_at"),
        kernel_run_id=d.get("kernel_run_id"),
        target_conversation_id=d.get("target_conversation_id"),
        result_summary=d.get("result_summary"),
        error=d.get("error"),
    )


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_request_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# CronExecutionService: unified scheduled + manual entry point
# ---------------------------------------------------------------------------


class CronRunnerPort(Protocol):
    """Public cron runner operations consumed by the execution owner."""

    async def submit(self, *, job: CronJob) -> tuple[str, str] | None: ...

    async def append_awareness(self, *, result_text: str) -> bool: ...


class CronTerminalConsumerPort(Protocol):
    """Consume one submitted cron run until its canonical terminal status."""

    async def consume(
        self, *, run_id: str, kernel_session_id: str, agent_id: str
    ) -> StreamRunOutcome: ...


class CronRunTerminalConsumer:
    """Consume cron kernel events with an optional owner-direct observer."""

    def __init__(
        self,
        *,
        kernel: Any,
        owner_user_id: str,
        run_context_store: RunDeliveryContextStore,
        observer: Callable[..., Any] | None = None,
    ) -> None:
        self._kernel = kernel
        self._owner_user_id = owner_user_id
        self._run_context_store = run_context_store
        self._observer = observer

    async def consume(
        self, *, run_id: str, kernel_session_id: str, agent_id: str
    ) -> StreamRunOutcome:
        """Consume one run, optionally translating events through IM delivery."""

        return await stream_run_to_completion(
            run_id=run_id,
            kernel_session_id=kernel_session_id,
            agent_id=agent_id,
            owner_user_id=self._owner_user_id,
            kernel=self._kernel,
            run_context_store=self._run_context_store,
            observer=self._observer,
        )


class CronExecutionService:
    """Unified cron execution entry point for scheduled and manual triggers.

    Both the scheduler tick and the manual run tool call enqueue(); both paths
    are guaranteed to use the same execution logic, delivery chain, and run history.

    The service validates the job, writes an accepted record, then owns submit,
    delivery, awareness, and terminal persistence in the background. It does not
    wait for execution to complete before returning.

    Args:
        agent_id: Agent whose jobs this service manages.
        workspace_root: Agent workspace root (for CronJobStore and CronRunsStore).
        runner: Public runner for isolated kernel submission and awareness.
        terminal_consumer: Mandatory terminal owner for runner-based execution.
            Its observer/delivery adapter may be absent, but Kernel terminal
            consumption itself is never optional.
        execute_fn: Compatibility injection for narrow callers. Production uses
            runner and terminal_consumer so the service owns the whole lifecycle.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        workspace_root: Path,
        runner: CronRunnerPort | None = None,
        terminal_consumer: CronTerminalConsumerPort | None = None,
        execute_fn: Callable[..., Awaitable[None]] | None = None,
        gateway_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        if runner is None and execute_fn is None:
            raise ValueError("CronExecutionService requires runner or execute_fn")
        if runner is not None and execute_fn is not None:
            raise ValueError("runner and execute_fn are mutually exclusive")
        if runner is not None and terminal_consumer is None:
            raise ValueError("runner-based cron execution requires terminal consumer")
        if execute_fn is not None and terminal_consumer is not None:
            raise ValueError("terminal consumer requires runner-based execution")
        self._runner = runner
        self._terminal_consumer = terminal_consumer
        self._execute_fn = execute_fn or self._execute_owned
        # Gateway asyncio loop reference for scheduling execute_fn when enqueue()
        # is called from a sync thread (e.g. tool.run() via asyncio.to_thread).
        # Without this, asyncio.get_event_loop() in the worker thread has no
        # running loop, and ensure_future silently drops the execution.
        self._gateway_loop = gateway_loop
        self._job_store = CronJobStore(workspace_root=self._workspace_root)
        self._runs_store = CronRunsStore(workspace_root=self._workspace_root)
        # bugfix-402-M6 W-1: track pending execute_fn Tasks so drain() can
        # await them before the IM connection is closed (Decision 7).
        self._pending_tasks: list[asyncio.Task] = []
        # bugfix-402 code-review: Context B (call_soon_threadsafe) has a window
        # between call_soon_threadsafe() returning and _schedule_with_tracking
        # executing where drain() would snapshot an empty _pending_tasks and miss
        # the in-flight task.  _pending_count tracks submitted-but-not-yet-done
        # executions (incremented before call_soon_threadsafe, decremented in the
        # Task done-callback).  drain() waits until the count reaches zero before
        # inspecting _pending_tasks — closing the registration window entirely.
        # threading.Lock protects the counter (modified from both loop and non-loop
        # threads) and the condition variable notifies drain() on each decrement.
        self._pending_count: int = 0
        self._pending_lock: threading.Lock = threading.Lock()
        self._pending_zero: threading.Condition = threading.Condition(
            self._pending_lock
        )
        self._sealed = False

    @property
    def runs_store(self) -> CronRunsStore:
        """Return the service-owned run history store."""
        return self._runs_store

    def converge_stale_on_restart(self) -> None:
        """Converge stale accepted or running records through the owned store."""

        self._runs_store.converge_stale_on_restart()

    async def _execute_owned(
        self, *, agent_id: str, job_id: str, request_id: str, trigger: str
    ) -> None:
        """Own accepted-to-terminal execution for production cron requests."""

        del trigger
        job = self._job_store.get(job_id)
        if job is None:
            self._runs_store.update_status(
                request_id,
                "failed",
                finished_at=_utc_now(),
                error="job_not_found",
            )
            return

        self._runs_store.update_status(request_id, "running", started_at=_utc_now())
        assert self._runner is not None
        try:
            submitted = await self._runner.submit(job=job)
        except Exception:  # noqa: BLE001
            _log.exception(
                "cron submit failed: agent=%s job=%s request=%s",
                agent_id,
                job_id,
                request_id,
            )
            submitted = None
        if submitted is None:
            self._runs_store.update_status(
                request_id,
                "failed",
                finished_at=_utc_now(),
                error="submit_failed",
            )
            return

        run_id, kernel_session_id = submitted
        self._runs_store.update_status(request_id, "running", kernel_run_id=run_id)
        assert self._terminal_consumer is not None

        try:
            outcome = await self._terminal_consumer.consume(
                run_id=run_id,
                kernel_session_id=kernel_session_id,
                agent_id=agent_id,
            )
        except Exception:  # noqa: BLE001
            _log.exception(
                "cron stream delivery failed: agent=%s job=%s run=%s",
                agent_id,
                job_id,
                run_id,
            )
            self._runs_store.update_status(
                request_id,
                "failed",
                finished_at=_utc_now(),
                error="stream_failed",
            )
            return

        result_summary = outcome.final_text[:200] or None
        if outcome.status != "completed":
            self._runs_store.update_status(
                request_id,
                outcome.status,
                finished_at=_utc_now(),
                result_summary=result_summary,
                error=outcome.error,
            )
            return

        self._runs_store.update_status(
            request_id,
            "completed",
            finished_at=_utc_now(),
            result_summary=result_summary,
        )
        if not outcome.final_text:
            return
        try:
            await self._runner.append_awareness(result_text=outcome.final_text)
        except Exception:  # noqa: BLE001
            _log.warning(
                "cron awareness injection failed: agent=%s job=%s",
                agent_id,
                job_id,
                exc_info=True,
            )

    def enqueue(
        self,
        *,
        job_id: str,
        trigger: str,
    ) -> Mapping[str, Any]:
        """Validate and accept a cron run request, returning a synchronous ack.

        Validates that the job exists and is enabled, writes an accepted record to
        runs.jsonl, and schedules execution via execute_fn.  Does not wait for
        the run to complete.

        Args:
            job_id: Job to execute.
            trigger: "scheduled" or "manual".

        Returns:
            CronEnqueueAck dict:
                accepted (bool): True when the request was accepted.
                job_id (str): Echo of the requested job_id.
                request_id (str | None): Stable request ID for history tracking.
                error_code (str | None): "job_not_found", "job_disabled", or "cron_unavailable".
        """
        # Register an admission token in the same tiny critical section as the seal
        # check. Shutdown may then set its O(1) seal without waiting for job-store I/O;
        # drain still observes this request until validation rejects it or its task ends.
        with self._pending_lock:
            if self._sealed:
                return self._rejected_ack(job_id, "cron_unavailable")
            self._pending_count += 1

        owns_pending_token = True
        try:
            job = self._job_store.get(job_id)
            if job is None:
                self._complete_pending()
                owns_pending_token = False
                return self._rejected_ack(job_id, "job_not_found")
            if not job.enabled:
                self._complete_pending()
                owns_pending_token = False
                return self._rejected_ack(job_id, "job_disabled")
            if self._sealed:
                self._complete_pending()
                owns_pending_token = False
                return self._rejected_ack(job_id, "cron_unavailable")

            request_id = _new_request_id()
            self._runs_store.append(
                CronRunRecord(
                    request_id=request_id,
                    job_id=job_id,
                    trigger=trigger,
                    status="accepted",
                    accepted_at=_utc_now(),
                )
            )
            coro = self._execute_fn(
                agent_id=self._agent_id,
                job_id=job_id,
                request_id=request_id,
                trigger=trigger,
            )

            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is not None:
                task = running_loop.create_task(coro, name=f"cron-execute-{request_id}")
                self._pending_tasks.append(task)
                task.add_done_callback(self._on_execution_done)
                owns_pending_token = False
            elif self._gateway_loop is not None and self._gateway_loop.is_running():

                def _schedule_with_tracking(c=coro) -> None:
                    assert self._gateway_loop is not None
                    task = self._gateway_loop.create_task(
                        c, name=f"cron-execute-{request_id}"
                    )
                    self._pending_tasks.append(task)
                    task.add_done_callback(self._on_execution_done)

                self._gateway_loop.call_soon_threadsafe(_schedule_with_tracking)
                owns_pending_token = False
            else:
                coro.close()
                self._complete_pending()
                owns_pending_token = False
                _log.warning(
                    "cron enqueue: no running event loop; execute_fn not scheduled "
                    "(agent=%s job=%s request=%s)",
                    self._agent_id,
                    job_id,
                    request_id,
                )

            return {
                "accepted": True,
                "job_id": job_id,
                "request_id": request_id,
                "error_code": None,
            }
        except BaseException:
            if owns_pending_token:
                self._complete_pending()
            raise

    @staticmethod
    def _rejected_ack(job_id: str, error_code: str) -> Mapping[str, Any]:
        return {
            "accepted": False,
            "job_id": job_id,
            "request_id": None,
            "error_code": error_code,
        }

    def _on_execution_done(self, task: asyncio.Task) -> None:
        if task in self._pending_tasks:
            self._pending_tasks.remove(task)
        self._complete_pending()

    def _complete_pending(self) -> None:
        with self._pending_zero:
            self._pending_count -= 1
            if self._pending_count == 0:
                self._pending_zero.notify_all()

    def request_stop(self) -> None:
        """Synchronously reject new cron execution admission."""

        self._sealed = True

    async def drain(self, deadline: float) -> None:
        """Await all pending execute_fn tasks by one absolute deadline.

        bugfix-402-M6 W-1: Decision 7 requires Gateway to drain in-flight cron
        executions before closing the IM transport so result delivery completes.
        Called from GatewayRuntime._run_until_shutdown() after kernel.aclose()
        and before im_connection_manager.close().

        bugfix-402 code-review fix: before snapshotting _pending_tasks, wait until
        _pending_count reaches zero.  This closes the Context B registration window
        where call_soon_threadsafe() has been issued but _schedule_with_tracking has
        not yet run on the event loop — without this gate, drain() could snapshot an
        empty _pending_tasks and return while the task is still in-flight.

        Args:
            deadline: Shared absolute Gateway ``loop.time()`` deadline. Tasks
                still running at the deadline are cancelled before returning.

        Raises:
            TimeoutError: When accepted work required deadline cancellation.
        """
        with self._pending_lock:
            already_zero = self._pending_count == 0

        if already_zero:
            return

        # Wait for all submitted executions to register their Task handles on the
        # event loop (closes the Context B window) and then complete.  We use
        # asyncio.to_thread so the threading.Condition.wait() does not block the
        # event loop while Context B callbacks are being dispatched.
        loop = asyncio.get_running_loop()

        def _wait_for_zero() -> bool:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            with self._pending_zero:
                while self._pending_count > 0:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        return False
                    self._pending_zero.wait(timeout=remaining)
                return True

        reached_zero = await asyncio.to_thread(_wait_for_zero)

        pending = list(self._pending_tasks)
        if not pending and reached_zero:
            return

        _log.debug(
            "cron drain: waiting for %d pending task(s) (agent=%s remaining=%.1fs)",
            len(pending),
            self._agent_id,
            max(0.0, deadline - loop.time()),
        )

        remaining_timeout = max(0.0, deadline - loop.time())
        try:
            if pending:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=remaining_timeout if reached_zero else 0.0,
                )
            elif not reached_zero:
                raise TimeoutError
        except (asyncio.TimeoutError, TimeoutError):
            _log.warning(
                "cron drain: %d task(s) exceeded Gateway deadline — cancelling (agent=%s)",
                len(self._pending_tasks),
                self._agent_id,
            )
            for task in list(self._pending_tasks):
                task.cancel()
            with suppress(Exception):
                await asyncio.gather(*list(self._pending_tasks), return_exceptions=True)
            raise TimeoutError(
                f"cron execution exceeded shutdown deadline: agent={self._agent_id}"
            ) from None
