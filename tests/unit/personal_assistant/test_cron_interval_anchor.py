"""Respect a configured interval start through the public scheduler tick."""

from datetime import UTC, datetime, timedelta

import pytest

from personal_assistant.scheduler.cron_scheduler import (
    CronJob,
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)


@pytest.mark.asyncio
async def test_interval_waits_for_anchor_and_keeps_alignment_after_restart(tmp_path):
    anchor = datetime(2026, 9, 10, 12, 0, 7, tzinfo=UTC)
    store = CronJobStore(workspace_root=tmp_path)
    store.add(
        CronJob(
            id="anchored",
            name="future interval",
            schedule={
                "kind": "every",
                "everyMs": 60_000,
                "anchorMs": int(anchor.timestamp() * 1000),
            },
            instruction="send the scheduled report",
        )
    )
    submitted = []

    async def submit(*, agent_id, job):
        submitted.append(job.id)

    state_path = tmp_path / "cron-state.json"

    def scheduler():
        return CronScheduler(
            agent_id="agent",
            job_store=store,
            state_store=CronSchedulerStateStore(state_path=state_path),
            submit_fn=submit,
        )

    clock = scheduler()
    await clock.tick(now=anchor - timedelta(days=1))
    await clock.tick(now=anchor - timedelta(milliseconds=1))
    assert submitted == []
    await clock.tick(now=anchor)
    assert submitted == ["anchored"]

    clock = scheduler()
    await clock.tick(now=anchor + timedelta(seconds=59))
    assert submitted == ["anchored"]
    await clock.tick(now=anchor + timedelta(seconds=63))
    assert submitted == ["anchored", "anchored"]
    await clock.tick(now=anchor + timedelta(minutes=10, seconds=3))
    await clock.tick(now=anchor + timedelta(minutes=10, seconds=4))
    assert submitted == ["anchored"] * 3
