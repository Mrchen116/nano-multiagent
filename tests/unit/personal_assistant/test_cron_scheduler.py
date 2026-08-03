"""Cron job-store persistence through its public operations."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore


def _job(job_id: str, *, enabled: bool, instruction: str) -> CronJob:
    return CronJob(
        id=job_id,
        name=job_id,
        schedule={"kind": "every", "everyMs": 60_000},
        instruction=instruction,
        enabled=enabled,
    )


def test_job_store_roundtrip_update_remove_and_enabled_filter(tmp_path: Path) -> None:
    """Persist job changes and exclude disabled jobs unless explicitly requested."""

    store = CronJobStore(workspace_root=tmp_path)
    store.add(_job("enabled", enabled=True, instruction="old"))
    store.add(_job("disabled", enabled=False, instruction="hidden"))

    reloaded = CronJobStore(workspace_root=tmp_path)
    assert [job.id for job in reloaded.list_jobs()] == ["enabled"]
    assert {job.id for job in reloaded.list_jobs(include_disabled=True)} == {
        "enabled",
        "disabled",
    }

    reloaded.update(_job("enabled", enabled=True, instruction="new"))
    reloaded.remove("disabled")

    final = CronJobStore(workspace_root=tmp_path).list_jobs(include_disabled=True)
    assert [(job.id, job.instruction) for job in final] == [("enabled", "new")]
