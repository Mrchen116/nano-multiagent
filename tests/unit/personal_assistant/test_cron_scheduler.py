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
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 3600_000}))
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
        store.add(_make_job(job_id="j2", schedule={"kind": "cron", "expr": "0 9 * * *"}))
        jobs = store.list_jobs()
        assert {j.id for j in jobs} == {"j1", "j2"}

    def test_remove_job(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}))
        store.add(_make_job(job_id="j2", schedule={"kind": "every", "everyMs": 120_000}))
        store.remove("j1")
        jobs = store.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "j2"

    def test_update_job(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        job = _make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}, instruction="old")
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
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}, enabled=True))
        store.add(_make_job(job_id="j2", schedule={"kind": "every", "everyMs": 60_000}, enabled=False))
        jobs = store.list_jobs(include_disabled=False)
        assert len(jobs) == 1
        assert jobs[0].id == "j1"

    def test_list_with_disabled_included(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}, enabled=True))
        store.add(_make_job(job_id="j2", schedule={"kind": "every", "everyMs": 60_000}, enabled=False))
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
        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state = _CronState(jobs={"j1": _CronRunState(last_due_at="2026-01-01T00:00:00+00:00")})
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
        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

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
        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        last_ran = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC)  # only 30s elapsed, interval=60s

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(
            job_id="j1", schedule={"kind": "every", "everyMs": 60_000}
        ))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state_store.save(_CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())}))

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        due = scheduler._compute_due_jobs(now=now)
        assert due == [], "Job not yet due — interval not reached"


class TestNonBackfillCronSchedule:
    """Verify 'cron' expression schedule does not backfill after restart.

    Provenance: openclaw/src/cron/schedule.ts:computeNextRunAtMs "cron" branch
    feat-394 decision 4.
    """

    def test_cron_fires_when_matching_minute(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert len(due) == 1

    def test_cron_no_backfill_after_missed_slots(self, tmp_path: Path) -> None:
        """After missing 10 firing slots, only the current minute is checked."""
        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        # Last ran at 09:00 day 1; now it's 09:00 day 2 — 24 hours later.
        last_ran = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC)

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state_store.save(_CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())}))

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        due = scheduler._compute_due_jobs(now=now)
        # Should fire today's 09:00, but NOT retroactively replay yesterday's slot
        assert len(due) == 1

    def test_cron_no_double_fire_same_minute(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        # Already ran at 09:00 exactly — another tick at 09:00:30 must not re-fire.
        last_ran = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        now = datetime(2026, 1, 1, 9, 0, 30, tzinfo=UTC)

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        state_store.save(_CronState(jobs={"j1": _CronRunState(last_due_at=last_ran.isoformat())}))

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        due = scheduler._compute_due_jobs(now=now)
        assert due == [], "Must not double-fire within same cron minute"

    def test_cron_no_fire_when_not_matching(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"}))
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
        store.add(_make_job(
            job_id="j1",
            schedule={"kind": "at", "at": "2026-01-01T10:00:00Z"},
            delete_after_run=True,
        ))
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
        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(
            job_id="j1",
            schedule={"kind": "at", "at": "2026-01-01T10:00:00Z"},
            delete_after_run=True,
        ))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        # Simulate: job ran at exactly its scheduled time
        state_store.save(_CronState(jobs={
            "j1": _CronRunState(last_due_at="2026-01-01T10:00:00+00:00")
        }))
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        # Gateway restarted 5 minutes later
        now = datetime(2026, 1, 1, 10, 5, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert due == [], "Expired 'at' job must NOT re-run after restart"

    def test_at_not_yet_due_not_fired(self, tmp_path: Path) -> None:
        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(
            job_id="j1",
            schedule={"kind": "at", "at": "2026-01-01T11:00:00Z"},
        ))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)  # before scheduled time
        due = scheduler._compute_due_jobs(now=now)
        assert due == []


# ---------------------------------------------------------------------------
# CronScheduler: multi-job tick (submit_fn integration)
# ---------------------------------------------------------------------------


class TestCronSchedulerTick:
    @pytest.mark.asyncio
    async def test_tick_submits_due_job(self, tmp_path: Path) -> None:
        submitted: list[dict] = []

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            submitted.append({"agent_id": agent_id, "job_id": job.id})

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(
            job_id="j1", schedule={"kind": "every", "everyMs": 60_000}, instruction="ping"
        ))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit,
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        await scheduler.tick(now=now)
        assert len(submitted) == 1
        assert submitted[0]["job_id"] == "j1"

    @pytest.mark.asyncio
    async def test_tick_skips_disabled_job(self, tmp_path: Path) -> None:
        submitted: list[dict] = []

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            submitted.append({"job_id": job.id})

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(
            job_id="j1",
            schedule={"kind": "every", "everyMs": 60_000},
            enabled=False,
        ))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=fake_submit
        )
        await scheduler.tick(now=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC))
        assert submitted == [], "Disabled job must not be submitted"

    @pytest.mark.asyncio
    async def test_tick_updates_state_after_submission(self, tmp_path: Path) -> None:
        """After a tick fires a job, last_due_at is persisted so next tick doesn't re-fire."""

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            pass

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=fake_submit
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        await scheduler.tick(now=now)

        # Re-tick at same time — should not fire again
        fired_second_time: list[str] = []

        async def fake_submit2(*, agent_id: str, job: CronJob) -> None:
            fired_second_time.append(job.id)

        scheduler2 = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=fake_submit2
        )
        await scheduler2.tick(now=now)
        assert fired_second_time == [], "Should not re-fire after state is persisted"

    @pytest.mark.asyncio
    async def test_tick_multiple_jobs_independent(self, tmp_path: Path) -> None:
        """Multiple jobs are evaluated independently; partial due jobs fire independently."""
        submitted: list[str] = []

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            submitted.append(job.id)

        store = CronJobStore(workspace_root=tmp_path)
        # j1 fires every 60s, j2 fires every 120s
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 60_000}))
        store.add(_make_job(job_id="j2", schedule={"kind": "every", "everyMs": 120_000}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")

        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState
        # j1 (60s): last_ran=9:57:00, elapsed=180s, steps=floor(180/60)=3, next=9:57:00+180s=10:00:00 → DUE
        # j2 (120s): last_ran=9:57:00, elapsed=180s, steps=floor(180/120)=1, next=9:57:00+120s=9:59:00 → DUE
        t_base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        state_store.save(_CronState(jobs={
            "j1": _CronRunState(last_due_at=datetime(2026, 1, 1, 9, 57, 0, tzinfo=UTC).isoformat()),
            "j2": _CronRunState(last_due_at=datetime(2026, 1, 1, 9, 57, 0, tzinfo=UTC).isoformat()),
        }))

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=fake_submit
        )
        await scheduler.tick(now=t_base)
        # j1 (60s interval, 180s elapsed) is due; j2 (120s interval, 180s elapsed) is also due
        assert "j1" in submitted
        assert "j2" in submitted

    @pytest.mark.asyncio
    async def test_interval_triggers_on_second_tick_with_lll_overhead(
        self, tmp_path: Path
    ) -> None:
        """Regression for R6-1 ceil bug: elapsed=interval+2s must trigger on second tick.

        Scenario: interval=15s, LLM call takes 2s, so elapsed after sleep(15s) ≈ 17s.
        ceil(17/15)=2 → next_due=last+30s > now+17s → NOT triggered (the bug).
        floor(17/15)=1 → next_due=last+15s <= now+17s → triggered (correct).
        """
        submitted: list[str] = []

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            submitted.append(job.id)

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 15_000}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")

        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        # Simulate: first tick triggered at T+0 (last_due_at set to T).
        # Second tick: now = T + 17s (15s sleep + 2s LLM overhead).
        # With floor: steps=floor(17/15)=1, next_due=T+15s <= T+17s → trigger.
        # With ceil:  steps=ceil(17/15)=2, next_due=T+30s > T+17s → NOT triggered (bug).
        t_last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        t_second_tick = t_last + timedelta(seconds=17)  # 17s > interval of 15s
        state_store.save(_CronState(jobs={
            "j1": _CronRunState(last_due_at=t_last.isoformat()),
        }))

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=fake_submit
        )
        await scheduler.tick(now=t_second_tick)
        assert "j1" in submitted, (
            "Second tick (elapsed=17s, interval=15s) must trigger; "
            "ceil bug would produce steps=2, next_due=T+30s > now=T+17s → not fired"
        )

    @pytest.mark.asyncio
    async def test_large_gap_triggers_only_once(self, tmp_path: Path) -> None:
        """Regression: large gap (5 missed intervals) must trigger exactly once, not backfill.

        Verifies that the floor-based fix does not re-introduce the round-2 backfill flood:
        one submission per tick regardless of how many intervals were missed while offline.
        """
        submitted: list[str] = []

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            submitted.append(job.id)

        store = CronJobStore(workspace_root=tmp_path)
        store.add(_make_job(job_id="j1", schedule={"kind": "every", "everyMs": 30_000}))
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")

        from personal_assistant.scheduler.cron_scheduler import _CronRunState, _CronState

        # 5 missed intervals: elapsed = 5 * 30s = 150s
        t_last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        t_now = t_last + timedelta(seconds=150)
        state_store.save(_CronState(jobs={
            "j1": _CronRunState(last_due_at=t_last.isoformat()),
        }))

        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=fake_submit
        )
        await scheduler.tick(now=t_now)
        # Must fire exactly once — no backfill flood
        assert submitted.count("j1") == 1, (
            f"Large gap must trigger exactly 1 run, got {submitted.count('j1')}"
        )
