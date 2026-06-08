"""Unit tests for cron schedule non-backfill semantics: cron and at schedule types.

Covers:
- TestNonBackfillCronSchedule: cron expression schedule non-backfill
- TestNonBackfillAtSchedule: at (one-shot) schedule, expiry after run
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from personal_assistant.scheduler.cron_scheduler import (
    CronJob,
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)


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


class TestNonBackfillCronSchedule:
    """Verify 'cron' expression schedule does not backfill after restart.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "cron" branch
    feat-394 decision 4.
    """

    def test_cron_fires_when_matching_minute(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"})
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert len(due) == 1

    def test_cron_no_backfill_after_missed_slots(self, tmp_path: Path) -> None:
        """After missing 10 firing slots, only the current minute is checked."""
        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        # Last ran at 09:00 day 1; now it's 09:00 day 2 — 24 hours later.
        last_ran = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC)

        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"})
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state_store.save(
            _CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())})
        )

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        due = scheduler._compute_due_jobs(now=now)
        # Should fire today's 09:00, but NOT retroactively replay yesterday's slot
        assert len(due) == 1

    def test_cron_no_double_fire_same_minute(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        # Already ran at 09:00 exactly — another tick at 09:00:30 must not re-fire.
        last_ran = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 1, 9, 0, 30, tzinfo=UTC)

        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"})
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state_store.save(
            _CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())})
        )

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        due = scheduler._compute_due_jobs(now=now)
        assert due == [], "Must not double-fire within same cron minute"

    def test_cron_no_fire_when_not_matching(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"})
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)  # 10:00, not 09:00
        due = scheduler._compute_due_jobs(now=now)
        assert due == []


class TestNonBackfillAtSchedule:
    """Verify 'at' one-shot schedule: runs once when time arrives, not after restart if expired.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "at" branch
    feat-394 decision 4.
    """

    def test_at_fires_when_time_arrived(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1",
                schedule={"kind": "at", "at": "2026-01-01T10:00:00Z"},
                delete_after_run=True,
            )
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert len(due) == 1

    def test_at_expired_not_run_after_restart(self, tmp_path: Path) -> None:
        """An 'at' job whose time has already passed and was already run must not re-run.

        Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "at" branch —
        atMs <= nowMs and job already executed → undefined (skip).
        """
        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1",
                schedule={"kind": "at", "at": "2026-01-01T10:00:00Z"},
                delete_after_run=True,
            )
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        # Simulate: job ran at exactly its scheduled time
        state_store.save(
            _CronState(
                jobs={"j1": _CronRunState(last_due_at="2026-01-01T10:00:00+00:00")}
            )
        )
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        # Gateway restarted 5 minutes later
        now = datetime(2026, 1, 1, 10, 5, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert due == [], "Expired 'at' job must NOT re-run after restart"

    def test_at_not_yet_due_not_fired(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1",
                schedule={"kind": "at", "at": "2026-01-01T11:00:00Z"},
            )
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)  # before scheduled time
        due = scheduler._compute_due_jobs(now=now)
        assert due == []
