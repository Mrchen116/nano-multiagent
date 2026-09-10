"""A journal failure is a failed cron submission, not an escaped scheduler task."""

import sqlite3

import pytest

from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_scheduler import CronJob
from tests.unit.personal_assistant.test_global_scheduled_work import agent_catalog


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["register", "record"])
async def test_cron_journal_failure_returns_failed_submission_and_can_retry(
    tmp_path, failure
):
    _, catalog = agent_catalog(tmp_path)
    submitted = []

    class Client:
        async def create_session(self, **kwargs):
            return {"session_id": "cron-session"}

        def submit_message(self, **kwargs):
            submitted.append(kwargs)
            return {"run_id": "cron-run"}

    class Recorder:
        failing = True

        def register(self, **kwargs):
            if self.failing and failure == "register":
                raise sqlite3.OperationalError("database is locked")

        def record(self, **kwargs):
            if self.failing and failure == "record":
                raise sqlite3.OperationalError("database is locked")

    recorder = Recorder()
    runner = CronRunner(
        agent_id="global",
        workspace_root=tmp_path,
        kernel_client=Client(),
        agent_catalog=catalog,
        work_recorder=recorder,
    )
    job = CronJob(
        id="job",
        name="check",
        schedule={"kind": "every", "everyMs": 1000},
        instruction="Check",
    )
    assert await runner.submit(job=job) is None
    assert not submitted
    recorder.failing = False
    assert await runner.submit(job=job) == ("cron-run", "cron-session")
