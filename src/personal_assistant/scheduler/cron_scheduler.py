"""Cron job scheduling engine for the personal assistant gateway.

Implements multi-job, per-agent cron scheduling with no backfill semantics
(openclaw computeNextRunAtMs) and persistence via per-agent workspace storage.

feat-394 decision 4: cron jobs run in isolated sessions (no conversation context).
feat-394 decision 4: restart never replays missed ticks — only the next future slot fires.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CronJob:
    """Describe one managed cron job.

    Args:
        id: Stable unique identifier (UUID).
        name: Human-readable label.
        schedule: Schedule descriptor dict; shape {kind: "at"|"every"|"cron", ...}.
            See SCHEDULE TYPES in the cron tool description.
        instruction: Prompt/message delivered to the agent at execution time.
        enabled: When False the job is skipped by the scheduler.
        delete_after_run: When True the job is removed after its first successful execution
            (one-shot 'at' semantics, openclaw deleteAfterRun).
    """

    id: str
    name: str
    schedule: dict[str, Any]
    instruction: str
    enabled: bool = True
    delete_after_run: bool = False


# ---------------------------------------------------------------------------
# Persistence: CronJobStore (per-agent workspace)
# ---------------------------------------------------------------------------

_CRON_SUBDIR = ".nanoassistant/cron"
_JOBS_FILENAME = "jobs.json"


class CronJobStore:
    """Persist cron job definitions to <workspace>/.nanoassistant/cron/jobs.json.

    Args:
        workspace_root: Agent workspace root directory.

    Notes:
        All writes are atomic enough for local single-process use (write-then-rename
        pattern is not used to keep the implementation simple; partial writes are
        unlikely on local SSD).
    """

    def __init__(self, workspace_root: Path) -> None:
        self._root = Path(workspace_root).expanduser().resolve()
        self._cron_dir = self._root / _CRON_SUBDIR
        self._jobs_path = self._cron_dir / _JOBS_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, job: CronJob) -> None:
        """Append one job; raises ValueError when id already exists."""
        jobs = self._read_all()
        if any(j.id == job.id for j in jobs):
            raise ValueError(f"cron job id already exists: {job.id}")
        jobs.append(job)
        self._write_all(jobs)

    def update(self, job: CronJob) -> None:
        """Replace an existing job by id; raises LookupError when not found."""
        jobs = self._read_all()
        idx = next((i for i, j in enumerate(jobs) if j.id == job.id), None)
        if idx is None:
            raise LookupError(f"cron job not found: {job.id}")
        jobs[idx] = job
        self._write_all(jobs)

    def remove(self, job_id: str) -> None:
        """Delete a job by id; no-op when id is not found."""
        jobs = self._read_all()
        filtered = [j for j in jobs if j.id != job_id]
        self._write_all(filtered)

    def get(self, job_id: str) -> CronJob | None:
        """Return one job by id, or None."""
        return next((j for j in self._read_all() if j.id == job_id), None)

    def list_jobs(self, *, include_disabled: bool = False) -> list[CronJob]:
        """Return all jobs, optionally filtering out disabled ones."""
        jobs = self._read_all()
        if include_disabled:
            return jobs
        return [j for j in jobs if j.enabled]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self._cron_dir.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[CronJob]:
        if not self._jobs_path.exists():
            return []
        raw = self._jobs_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        jobs: list[CronJob] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                jobs.append(_job_from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        return jobs

    def _write_all(self, jobs: list[CronJob]) -> None:
        self._ensure_dir()
        serialized = [_job_to_dict(j) for j in jobs]
        self._jobs_path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _job_to_dict(job: CronJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "name": job.name,
        "schedule": dict(job.schedule),
        "instruction": job.instruction,
        "enabled": job.enabled,
        "delete_after_run": job.delete_after_run,
    }


def _job_from_dict(d: dict[str, Any]) -> CronJob:
    return CronJob(
        id=str(d["id"]),
        name=str(d.get("name", "")),
        schedule=dict(d["schedule"]) if isinstance(d.get("schedule"), dict) else {},
        instruction=str(d.get("instruction", "")),
        enabled=bool(d.get("enabled", True)),
        delete_after_run=bool(d.get("delete_after_run", False)),
    )


# ---------------------------------------------------------------------------
# Persistence: CronSchedulerStateStore (per-agent runtime state)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _CronRunState:
    last_due_at: str | None = None


@dataclass
class _CronState:
    jobs: dict[str, _CronRunState] = field(default_factory=dict)


class CronSchedulerStateStore:
    """Persist per-job last-due timestamps for non-backfill scheduling.

    Args:
        state_path: JSON file path for run state storage.
    """

    def __init__(self, state_path: Path) -> None:
        self._path = Path(state_path).expanduser().resolve()

    def load(self) -> _CronState:
        if not self._path.exists():
            return _CronState()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (ValueError, TypeError):
            return _CronState()
        if not isinstance(raw, dict):
            return _CronState()
        jobs_raw = raw.get("jobs", {})
        if not isinstance(jobs_raw, dict):
            return _CronState()
        jobs: dict[str, _CronRunState] = {}
        for job_id, payload in jobs_raw.items():
            if not isinstance(job_id, str) or not isinstance(payload, dict):
                continue
            last_due_at = payload.get("last_due_at")
            if last_due_at is not None and not isinstance(last_due_at, str):
                continue
            jobs[job_id] = _CronRunState(last_due_at=last_due_at)
        return _CronState(jobs=jobs)

    def save(self, state: _CronState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {
            "jobs": {
                job_id: {"last_due_at": rs.last_due_at}
                for job_id, rs in state.jobs.items()
            }
        }
        self._path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Schedule primitives (non-backfill, openclaw computeNextRunAtMs semantics)
# ---------------------------------------------------------------------------

_INTERVAL_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_WEEKDAY_NAME_TO_CRON = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
}


class _Schedule(Protocol):
    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]: ...


@dataclass(frozen=True, slots=True)
class _AtSchedule:
    """One-shot schedule: fires once when time arrives, never after already executed.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "at" branch —
    returns undefined when atMs <= nowMs (meaning job is not future, skip).
    feat-394 decision 4: expired 'at' jobs are not re-run after gateway restart.
    """

    due_at: datetime

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        if now < self.due_at:
            return []
        if last_due_at is not None and last_due_at >= self.due_at:
            return []
        return [self.due_at]


@dataclass(frozen=True, slots=True)
class _IntervalSchedule:
    """Recurring interval schedule with no backfill.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "every" branch —
    steps = ceil(elapsed / everyMs), next = anchor + steps * everyMs.
    Result is always the first future slot; a restart gap never replays past ticks.
    feat-394 decision 4: only ONE run emitted per tick regardless of missed intervals.
    """

    interval: timedelta

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        if last_due_at is None:
            return [_floor_datetime(now, self.interval)]
        elapsed = now - last_due_at
        if elapsed <= timedelta(0):
            return []
        interval_secs = int(self.interval.total_seconds())
        elapsed_secs = int(elapsed.total_seconds())
        steps = max(1, (elapsed_secs + interval_secs - 1) // interval_secs)
        next_due_at = last_due_at + self.interval * steps
        if next_due_at > now:
            return []
        return [next_due_at]


@dataclass(frozen=True, slots=True)
class _CronSchedule:
    """Cron-expression schedule; fires at most once per matching minute, no backfill.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "cron" branch —
    openclaw checks now >= next_run_at per tick then immediately advances to the next
    future match.  Net effect: only the current minute fires if it matches AND hasn't
    already fired.  A restart never replays past matching minutes.
    feat-394 decision 4.
    """

    minute_values: tuple[int, ...]
    hour_values: tuple[int, ...]
    day_values: tuple[int, ...]
    month_values: tuple[int, ...]
    weekday_values: tuple[int, ...]

    def due_times_up_to(
        self, *, now: datetime, last_due_at: datetime | None
    ) -> list[datetime]:
        current = now.replace(second=0, microsecond=0)
        if not self._matches(current):
            return []
        if last_due_at is not None and last_due_at.replace(second=0, microsecond=0) == current:
            return []
        return [current]

    def _matches(self, candidate: datetime) -> bool:
        cron_weekday = (candidate.weekday() + 1) % 7
        return (
            candidate.minute in self.minute_values
            and candidate.hour in self.hour_values
            and candidate.day in self.day_values
            and candidate.month in self.month_values
            and cron_weekday in self.weekday_values
        )


# ---------------------------------------------------------------------------
# Schedule parsing
# ---------------------------------------------------------------------------


def _parse_schedule_dict(schedule: dict[str, Any]) -> _Schedule:
    """Parse a CronJob.schedule dict into a _Schedule instance.

    Args:
        schedule: Dict with at least a 'kind' key; shape matches openclaw job schema.

    Raises:
        ValueError: When kind is unknown or required fields are missing/malformed.
    """
    kind = schedule.get("kind")
    if kind == "at":
        at_str = schedule.get("at")
        if not isinstance(at_str, str) or not at_str.strip():
            raise ValueError("'at' schedule requires 'at' field (ISO-8601 string)")
        due_at = _normalize_datetime(datetime.fromisoformat(at_str.strip()))
        return _AtSchedule(due_at=due_at)
    elif kind == "every":
        every_ms_raw = schedule.get("everyMs")
        if every_ms_raw is None:
            raise ValueError("'every' schedule requires 'everyMs' field")
        every_ms = int(every_ms_raw)
        if every_ms <= 0:
            raise ValueError("'every.everyMs' must be positive")
        interval = timedelta(milliseconds=every_ms)
        return _IntervalSchedule(interval=interval)
    elif kind == "cron":
        expr = schedule.get("expr")
        if not isinstance(expr, str) or not expr.strip():
            raise ValueError("'cron' schedule requires 'expr' field")
        return _parse_cron(expr.strip())
    else:
        raise ValueError(f"unsupported cron schedule kind: {kind!r}")


def _parse_cron(raw_value: str) -> _CronSchedule:
    parts = raw_value.split()
    if len(parts) != 5:
        raise ValueError(f"cron expression must have 5 fields: {raw_value!r}")
    minute, hour, day, month, weekday = parts
    return _CronSchedule(
        minute_values=_parse_cron_field(minute, minimum=0, maximum=59),
        hour_values=_parse_cron_field(hour, minimum=0, maximum=23),
        day_values=_parse_cron_field(day, minimum=1, maximum=31),
        month_values=_parse_cron_field(month, minimum=1, maximum=12),
        weekday_values=_parse_cron_field(
            weekday, minimum=0, maximum=6, allow_names=True
        ),
    )


def _parse_cron_field(
    field_str: str,
    *,
    minimum: int,
    maximum: int,
    allow_names: bool = False,
) -> tuple[int, ...]:
    if field_str == "*":
        return tuple(range(minimum, maximum + 1))
    values: set[int] = set()
    for item in field_str.split(","):
        item = item.strip()
        if "/" in item:
            base, step_str = item.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"cron step must be positive: {step_str!r}")
            if "-" in base:
                start_text, end_text = base.split("-", 1)
                start = _parse_cron_number(start_text, allow_names=allow_names)
                end = _parse_cron_number(end_text, allow_names=allow_names)
            else:
                start = minimum if base == "*" else _parse_cron_number(base, allow_names=allow_names)
                end = maximum
            values.update(range(start, end + 1, step))
        elif "-" in item:
            start_text, end_text = item.split("-", 1)
            start = _parse_cron_number(start_text, allow_names=allow_names)
            end = _parse_cron_number(end_text, allow_names=allow_names)
            values.update(range(start, end + 1))
        else:
            values.add(_parse_cron_number(item, allow_names=allow_names))
    return tuple(sorted(v for v in values if minimum <= v <= maximum))


def _parse_cron_number(text: str, *, allow_names: bool = False) -> int:
    text = text.strip().lower()
    if allow_names and text in _WEEKDAY_NAME_TO_CRON:
        return _WEEKDAY_NAME_TO_CRON[text]
    return int(text)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_optional_datetime(text: str | None) -> datetime | None:
    if text is None:
        return None
    return _normalize_datetime(datetime.fromisoformat(text))


def _floor_datetime(value: datetime, interval: timedelta) -> datetime:
    seconds = int(interval.total_seconds())
    if seconds <= 0:
        raise ValueError("interval must be positive")
    timestamp = int(value.timestamp())
    floored = timestamp - (timestamp % seconds)
    return datetime.fromtimestamp(floored, tz=UTC)


# ---------------------------------------------------------------------------
# CronScheduler: per-agent multi-job scheduler
# ---------------------------------------------------------------------------


class CronScheduler:
    """Evaluate per-agent cron jobs and submit due runs to the kernel.

    Args:
        agent_id: The agent whose jobs this scheduler evaluates.
        job_store: Persistent store for job definitions (workspace-bound).
        state_store: Persistent store for per-job last-due timestamps.
        submit_fn: Async callable invoked for each due job.
            Signature: ``async def submit_fn(*, agent_id: str, job: CronJob) -> None``
            Pass None to use the scheduler in read-only mode (for testing _compute_due_jobs).

    Notes:
        One CronScheduler instance is created per agent per PollingCronRunner tick;
        alternatively, one shared instance per gateway tick evaluating all agents.
        feat-394 decision 4: isolated execution and non-backfill semantics.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        job_store: CronJobStore,
        state_store: CronSchedulerStateStore,
        submit_fn: Callable[..., Awaitable[None]] | None,
    ) -> None:
        self._agent_id = agent_id
        self._job_store = job_store
        self._state_store = state_store
        self._submit_fn = submit_fn

    async def tick(self, *, now: datetime | None = None) -> None:
        """Evaluate all enabled jobs and submit due ones.

        Args:
            now: Current time; defaults to UTC now.
        """
        current_time = _normalize_datetime(now or datetime.now(tz=UTC))
        due_jobs = self._compute_due_jobs(now=current_time)
        if not due_jobs or self._submit_fn is None:
            return
        state = self._state_store.load()
        state_jobs = dict(state.jobs)
        for job in due_jobs:
            await self._submit_fn(agent_id=self._agent_id, job=job)
            # Record the due time regardless of delete_after_run, so the job
            # is not re-submitted if still present.
            due_at = self._compute_single_due_time(job, state=state, now=current_time)
            state_jobs[job.id] = _CronRunState(
                last_due_at=due_at.isoformat() if due_at else current_time.isoformat()
            )
            if job.delete_after_run:
                self._job_store.remove(job.id)
        self._state_store.save(_CronState(jobs=state_jobs))

    def _compute_due_jobs(self, *, now: datetime) -> list[CronJob]:
        """Return all enabled jobs that are due at `now`, using persisted state."""
        state = self._state_store.load()
        jobs = self._job_store.list_jobs(include_disabled=False)
        due: list[CronJob] = []
        for job in jobs:
            last_run = _parse_optional_datetime(state.jobs.get(job.id, _CronRunState()).last_due_at)
            try:
                schedule = _parse_schedule_dict(job.schedule)
            except (ValueError, KeyError):
                continue
            if schedule.due_times_up_to(now=now, last_due_at=last_run):
                due.append(job)
        return due

    def _compute_single_due_time(
        self, job: CronJob, *, state: _CronState, now: datetime
    ) -> datetime | None:
        last_run = _parse_optional_datetime(state.jobs.get(job.id, _CronRunState()).last_due_at)
        try:
            schedule = _parse_schedule_dict(job.schedule)
        except (ValueError, KeyError):
            return None
        times = schedule.due_times_up_to(now=now, last_due_at=last_run)
        return times[0] if times else now


def make_cron_job_id() -> str:
    """Generate a stable unique cron job identifier."""
    return uuid.uuid4().hex
