"""Unified cron execution service: scheduled and manual runs share one entry point.

bugfix-402 Decision 2: Gateway has exactly one CronExecutionService; both the scheduler
tick and the manual run tool call the same enqueue() method.

The service is responsible for:
- Validating job exists and is enabled (before creating any state)
- Persisting an "accepted" record to runs.jsonl
- Dispatching execution via execute_fn (injected at construction)
- Tracking accepted→running→terminal state transitions in runs.jsonl

runs.jsonl lives at <workspace>/.nanoassistant/cron/runs.jsonl (append-only).
State is materialized per request_id by replaying the log.

On gateway restart, converge_stale_on_restart() marks any accepted/running records
as failed(gateway_restarted) so they never stay permanently "in progress".
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

import logging

from personal_assistant.scheduler.cron_scheduler import CronJobStore

_log = logging.getLogger(__name__)

_CRON_SUBDIR = ".nanoassistant/cron"
_RUNS_FILENAME = "runs.jsonl"

# Maximum number of terminal records to retain per job.
_MAX_TERMINAL_RECORDS_PER_JOB = 100


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, record: CronRunRecord) -> None:
        """Append one record to runs.jsonl.  Thread-unsafe; callers serialize."""
        self._ensure_dir()
        line = json.dumps(asdict(record), ensure_ascii=False)
        with self._runs_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

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
        # Read the existing record to carry forward immutable fields.
        all_records = self._materialize_all()
        existing = all_records.get(request_id)
        if existing is None:
            _log.warning(
                "cron runs: update_status for unknown request_id=%r (store may be inconsistent)",
                request_id,
            )
            # Still append; the materializer will produce a partial record.
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
            target_conversation_id=target_conversation_id or existing.target_conversation_id,
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
        all_records = self._materialize_all()
        stale = [
            r for r in all_records.values()
            if r.status in ("accepted", "running")
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
        """Replay runs.jsonl and return latest state per request_id."""
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
        return records


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


class CronExecutionService:
    """Unified cron execution entry point for scheduled and manual triggers.

    Both the scheduler tick and the manual run tool call enqueue(); both paths
    are guaranteed to use the same execution logic, delivery chain, and run history.

    The service validates the job, writes an accepted record, then calls execute_fn
    in the background.  It does NOT wait for execution to complete before returning.

    Args:
        agent_id: Agent whose jobs this service manages.
        workspace_root: Agent workspace root (for CronJobStore and CronRunsStore).
        execute_fn: Async callable invoked for each accepted request.
            Signature: async def execute_fn(*, agent_id, job_id, request_id, trigger) -> None
            The service writes accepted; execute_fn is responsible for updating to
            running and terminal states via the injected CronRunsStore.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        workspace_root: Path,
        execute_fn: Callable[..., Awaitable[None]],
    ) -> None:
        self._agent_id = agent_id
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._execute_fn = execute_fn
        self._job_store = CronJobStore(workspace_root=self._workspace_root)
        self._runs_store = CronRunsStore(workspace_root=self._workspace_root)

    @property
    def runs_store(self) -> CronRunsStore:
        """Expose the runs store so execute_fn implementations can update history."""
        return self._runs_store

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
        job = self._job_store.get(job_id)
        if job is None:
            return {
                "accepted": False,
                "job_id": job_id,
                "request_id": None,
                "error_code": "job_not_found",
            }
        if not job.enabled:
            return {
                "accepted": False,
                "job_id": job_id,
                "request_id": None,
                "error_code": "job_disabled",
            }

        request_id = _new_request_id()
        now = _utc_now()

        # Persist accepted record before dispatching execute_fn.
        self._runs_store.append(CronRunRecord(
            request_id=request_id,
            job_id=job_id,
            trigger=trigger,
            status="accepted",
            accepted_at=now,
        ))

        # Schedule execution (fire-and-forget from caller's perspective).
        # execute_fn is responsible for calling runs_store.update_status().
        import asyncio  # noqa: PLC0415

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Called from Gateway asyncio loop: schedule coroutine directly.
            asyncio.ensure_future(
                self._execute_fn(
                    agent_id=self._agent_id,
                    job_id=job_id,
                    request_id=request_id,
                    trigger=trigger,
                )
            )
        else:
            # Called from background thread (RunsRegistry): schedule via loop.call_soon_threadsafe.
            # The executor is responsible for providing a loop via _gateway_loop injection.
            # For now, log a warning — this path is not reached in normal Gateway operation.
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
