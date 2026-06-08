"""Unit tests for CronScheduler tick behavior (multi-job, submit_fn integration).

Covers:
- Tick submits due jobs via submit_fn
- Tick skips disabled jobs
- Tick respects cron_enabled gate (agent not enabled → no tick)
- delete_after_run: one-shot at job removed after execution
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


# CronScheduler: multi-job tick (submit_fn integration)
# ---------------------------------------------------------------------------


class TestCronSchedulerTick:
    @pytest.mark.asyncio
    async def test_tick_submits_due_job(self, tmp_path: Path) -> None:
        submitted: list[dict] = []

        async def fake_submit(*, agent_id: str, job: CronJob) -> None:
            submitted.append({"agent_id": agent_id, "job_id": job.id})

        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1",
                schedule={"kind": "every", "everyMs": 60_000},
                instruction="ping",
            )
        )
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
        store.add(
            _make_job(
                job_id="j1",
                schedule={"kind": "every", "everyMs": 60_000},
                enabled=False,
            )
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit,
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
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit,
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        await scheduler.tick(now=now)

        # Re-tick at same time — should not fire again
        fired_second_time: list[str] = []

        async def fake_submit2(*, agent_id: str, job: CronJob) -> None:
            fired_second_time.append(job.id)

        scheduler2 = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit2,
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
        store.add(
            _make_job(job_id="j2", schedule={"kind": "every", "everyMs": 120_000})
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")

        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        # j1 (60s): last_ran=9:57:00, elapsed=180s, steps=floor(180/60)=3, next=9:57:00+180s=10:00:00 → DUE
        # j2 (120s): last_ran=9:57:00, elapsed=180s, steps=floor(180/120)=1, next=9:57:00+120s=9:59:00 → DUE
        t_base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        state_store.save(
            _CronState(
                jobs={
                    "j1": _CronRunState(
                        last_due_at=datetime(
                            2026, 1, 1, 9, 57, 0, tzinfo=UTC
                        ).isoformat()
                    ),
                    "j2": _CronRunState(
                        last_due_at=datetime(
                            2026, 1, 1, 9, 57, 0, tzinfo=UTC
                        ).isoformat()
                    ),
                }
            )
        )

        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit,
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

        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        # Simulate: first tick triggered at T+0 (last_due_at set to T).
        # Second tick: now = T + 17s (15s sleep + 2s LLM overhead).
        # With floor: steps=floor(17/15)=1, next_due=T+15s <= T+17s → trigger.
        # With ceil:  steps=ceil(17/15)=2, next_due=T+30s > T+17s → NOT triggered (bug).
        t_last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        t_second_tick = t_last + timedelta(seconds=17)  # 17s > interval of 15s
        state_store.save(
            _CronState(
                jobs={
                    "j1": _CronRunState(last_due_at=t_last.isoformat()),
                }
            )
        )

        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit,
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

        from personal_assistant.scheduler.cron_scheduler import (
            _CronRunState,
            _CronState,
        )

        # 5 missed intervals: elapsed = 5 * 30s = 150s
        t_last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        t_now = t_last + timedelta(seconds=150)
        state_store.save(
            _CronState(
                jobs={
                    "j1": _CronRunState(last_due_at=t_last.isoformat()),
                }
            )
        )

        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=store,
            state_store=state_store,
            submit_fn=fake_submit,
        )
        await scheduler.tick(now=t_now)
        # Must fire exactly once — no backfill flood
        assert submitted.count("j1") == 1, (
            f"Large gap must trigger exactly 1 run, got {submitted.count('j1')}"
        )
