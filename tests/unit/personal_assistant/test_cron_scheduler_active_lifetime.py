"""Regression tests for one-shot cron jobs across a Gateway process lifetime.

The scheduler must distinguish a task missed while the Gateway was offline from
one delayed while the same Gateway process remains alive.  Both cases can have
no persisted run state, but only the latter remains an actionable user request.
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


def _one_shot_job(*, due_at: datetime) -> CronJob:
    return CronJob(
        id="one-shot",
        name="one-shot reminder",
        schedule={"kind": "at", "at": due_at.isoformat()},
        instruction="Send the reminder.",
    )


class TestCronSchedulerActiveLifetime:
    def test_late_one_shot_fires_when_gateway_was_active_before_due_time(
        self, tmp_path: Path
    ) -> None:
        """A live Gateway must deliver a one-shot despite a delayed polling tick."""
        due_at = datetime(2026, 7, 14, 5, 14, 30, tzinfo=UTC)
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(_one_shot_job(due_at=due_at))
        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=job_store,
            state_store=CronSchedulerStateStore(
                state_path=tmp_path / "cron-state.json"
            ),
            submit_fn=None,
            active_since=due_at - timedelta(minutes=1),
        )

        due_jobs = scheduler._compute_due_jobs(now=due_at + timedelta(seconds=107))

        assert [job.id for job in due_jobs] == ["one-shot"]

    def test_one_shot_missed_before_gateway_started_is_not_backfilled(
        self, tmp_path: Path
    ) -> None:
        """A restart must still not replay a one-shot that expired while offline."""
        due_at = datetime(2026, 7, 14, 5, 14, 30, tzinfo=UTC)
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(_one_shot_job(due_at=due_at))
        scheduler = CronScheduler(
            agent_id="agent-1",
            job_store=job_store,
            state_store=CronSchedulerStateStore(
                state_path=tmp_path / "cron-state.json"
            ),
            submit_fn=None,
            active_since=due_at + timedelta(minutes=1),
        )

        due_jobs = scheduler._compute_due_jobs(now=due_at + timedelta(hours=7))

        assert due_jobs == []
