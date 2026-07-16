"""Linearized manual cron admission at Gateway shutdown."""

from __future__ import annotations

import asyncio
import threading

import pytest

from personal_assistant.scheduler.cron_execution_service import CronExecutionService
from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore


@pytest.mark.asyncio
async def test_request_stop_cannot_pass_acceptance_before_task_registration(
    tmp_path,
) -> None:
    """Seal waits for a begun enqueue to register work before drain can observe zero."""

    lookup_started = threading.Event()
    release_lookup = threading.Event()
    execution_started = asyncio.Event()
    release_execution = asyncio.Event()

    async def _execute(**_kwargs: object) -> None:
        execution_started.set()
        await release_execution.wait()

    CronJobStore(workspace_root=tmp_path).add(
        CronJob(
            id="job-1",
            name="linearized admission",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="test",
        )
    )
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        execute_fn=_execute,
        gateway_loop=asyncio.get_running_loop(),
    )
    original_get = service._job_store.get  # noqa: SLF001

    def _blocking_get(job_id: str):
        lookup_started.set()
        assert release_lookup.wait(timeout=1)
        return original_get(job_id)

    service._job_store.get = _blocking_get  # type: ignore[method-assign]  # noqa: SLF001

    enqueue = asyncio.create_task(
        asyncio.to_thread(service.enqueue, job_id="job-1", trigger="manual")
    )
    assert await asyncio.to_thread(lookup_started.wait, 1)
    service.request_stop()
    drain = asyncio.create_task(service.drain(asyncio.get_running_loop().time() + 1))
    await asyncio.sleep(0.05)
    drained_before_registration = drain.done()
    release_lookup.set()
    ack = await enqueue
    if ack["accepted"]:
        await asyncio.wait_for(execution_started.wait(), timeout=1)
        release_execution.set()
    await drain

    assert ack == {
        "accepted": False,
        "job_id": "job-1",
        "request_id": None,
        "error_code": "cron_unavailable",
    }
    assert drained_before_registration is False
