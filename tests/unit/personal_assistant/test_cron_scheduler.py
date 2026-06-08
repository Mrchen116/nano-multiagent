"""Unit tests for feat-394-M2 cron subsystem.

Covers:
- CronJobStore persistence (add/list/update/remove)
- CronScheduler multi-job tick: due detection, not-yet-due skip
- Non-backfill semantics (openclaw computeNextRunAtMs) for every/cron/at schedules
- cron_enabled per-agent gate
- delete_after_run for one-shot at jobs
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from personal_assistant.scheduler.cron_scheduler import (
    CronJob,
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_job(
    *,
    job_id: str = "job-1",
    name: str = "test job",
    schedule: dict,
    instruction: str = "Do something",
    enabled: bool = True,
    delete_after_run: bool = False,
) -> CronJob:
    return CronJob(
        id=job_id,
        name=name,
        schedule=schedule,
        instruction=instruction,
        enabled=enabled,
        delete_after_run=delete_after_run,
    )


# ---------------------------------------------------------------------------
# CronJob dataclass
# ---------------------------------------------------------------------------


class TestCronJob:
    def test_cron_job_has_expected_fields(self) -> None:
        job = _make_job(
            job_id="j1",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="ping",
        )
        assert job.id == "j1"
        assert job.schedule == {"kind": "every", "everyMs": 60_000}
        assert job.instruction == "ping"
        assert job.enabled is True
        assert job.delete_after_run is False

    def test_cron_job_delete_after_run_default_false(self) -> None:
        job = _make_job(schedule={"kind": "at", "at": "2030-01-01T00:00:00Z"})
        assert job.delete_after_run is False


# ---------------------------------------------------------------------------
# CronJobStore (per-agent workspace persistence)
# ---------------------------------------------------------------------------


class TestCronJobStore:
    def test_add_and_list(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        job = _make_job(job_id="j1", schedule={"kind": "every", "everyMs": 3600_000})
        store.add(job)
        jobs = store.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "j1"

    def test_jobs_persisted_to_disk(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(job_id="j1", schedule={"kind": "every", "everyMs": 3600_000})
        )
        # Re-create store to verify persistence
        store2 = CronJobStore(workspace_root=tmp_path)
        jobs = store2.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "j1"

    def test_jobs_file_path(self, tmp_path: Path) -> None:
        """CronJobStore must write to <workspace>/.nanoassistant/cron/jobs.json."""
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(schedule={"kind": "every", "everyMs": 60_000}))
        jobs_path = tmp_path / ".nanoassistant" / "cron" / "jobs.json"
        assert jobs_path.exists(), "jobs.json must be under .nanoassistant/cron/"

    def test_add_multiple_jobs(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}))
        store.add(
            _make_job(job_id="j2", schedule={"kind": "cron", "expr": "0 9 * * *"})
        )
        jobs = store.list_jobs()
        assert {j.id for j in jobs} == {"j1", "j2"}

    def test_remove_job(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}))
        store.add(
            _make_job(job_id="j2", schedule={"kind": "every", "everyMs": 120_000})
        )
        store.remove("j1")
        jobs = store.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "j2"

    def test_update_job(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        job = _make_job(
            job_id="j1",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="old",
        )
        store.add(job)
        updated_job = CronJob(
            id="j1",
            name=job.name,
            schedule={"kind": "every", "everyMs": 120_000},
            instruction="new",
            enabled=True,
            delete_after_run=False,
        )
        store.update(updated_job)
        jobs = store.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].instruction == "new"
        assert jobs[0].schedule["everyMs"] == 120_000

    def test_list_disabled_excluded_by_default(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1", schedule={"kind": "every", "everyMs": 60_000}, enabled=True
            )
        )
        store.add(
            _make_job(
                job_id="j2",
                schedule={"kind": "every", "everyMs": 60_000},
                enabled=False,
            )
        )
        jobs = store.list_jobs(include_disabled=False)
        assert len(jobs) == 1
        assert jobs[0].id == "j1"

    def test_list_with_disabled_included(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1", schedule={"kind": "every", "everyMs": 60_000}, enabled=True
            )
        )
        store.add(
            _make_job(
                job_id="j2",
                schedule={"kind": "every", "everyMs": 60_000},
                enabled=False,
            )
        )
        jobs = store.list_jobs(include_disabled=True)
        assert len(jobs) == 2

    def test_remove_nonexistent_is_noop(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        # Should not raise
        store.remove("nonexistent")

    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        assert store.list_jobs() == []


# ---------------------------------------------------------------------------
# CronSchedulerStateStore
# ---------------------------------------------------------------------------


class TestCronSchedulerStateStore:
    def test_load_empty_when_file_missing(self, tmp_path: Path) -> None:
        store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state = store.load()
        assert state.jobs == {}

    def test_save_and_reload(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state = _CronState(
            jobs={"j1": _CronRunState(last_due_at="2026-01-01T00:00:00+00:00")}
        )
        store.save(state)
        loaded = store.load()
        assert loaded.jobs["j1"].last_due_at == "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Non-backfill scheduling semantics (openclaw computeNextRunAtMs)
# ---------------------------------------------------------------------------


class TestNonBackfillEverySchedule:
    """Verify 'every' schedule (interval) does not backfill after restart.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "every" branch
    feat-394 decision 4.
    """

    def test_first_tick_triggers_immediately(self, tmp_path: Path) -> None:
        """First tick with no last_due triggers at floor(now, interval)."""
        store = CronJobStore(workspace_root=tmp_path)
        job = _make_job(
            job_id="j1",
            schedule={"kind": "every", "everyMs": 60_000},  # every 60s
            instruction="check",
        )
        store.add(job)
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=None,
        )
        now = datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC)  # 10:00:30
        due = scheduler._compute_due_jobs(now=now)
        assert len(due) == 1
        assert due[0].id == "j1"

    def test_no_backfill_after_long_gap(self, tmp_path: Path) -> None:
        """After a restart gap of 5 intervals, only 1 run is emitted (not 5).

        Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "every" branch —
        steps = ceil(elapsed/everyMs) always lands on the next future slot after anchor.
        """
        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        # Last ran at 10:00; now it's 10:05 — gap = 5 minutes, interval = 60s → 5 missed ticks.
        last_ran = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 1, 10, 5, 0, tzinfo=UTC)

        store = CronJobStore(workspace_root=tmp_path)
        job = _make_job(
            job_id="j1",
            schedule={"kind": "every", "everyMs": 60_000},
        )
        store.add(job)

        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state = _CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())})
        state_store.save(state)

        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=None,
        )
        due = scheduler._compute_due_jobs(now=now)
        # openclaw semantics: only ONE run at the next aligned slot, not 5
        assert len(due) == 1, f"Expected 1 due job (not backfill), got {len(due)}"

    def test_not_due_when_interval_not_reached(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        last_ran = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        now = datetime(
            2026, 1, 1, 10, 0, 30, tzinfo=UTC
        )  # only 30s elapsed, interval=60s

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state_store.save(
            _CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())})
        )

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        due = scheduler._compute_due_jobs(now=now)
        assert due == [], "Job not yet due — interval not reached"
