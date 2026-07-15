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
    stop_returned = threading.Event()
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

    def _stop() -> None:
        service.request_stop()
        stop_returned.set()

    enqueue = asyncio.create_task(
        asyncio.to_thread(service.enqueue, job_id="job-1", trigger="manual")
    )
    assert await asyncio.to_thread(lookup_started.wait, 1)
    stop = asyncio.create_task(asyncio.to_thread(_stop))
    stopped_before_registration = await asyncio.to_thread(stop_returned.wait, 0.05)
    release_lookup.set()
    ack = await enqueue
    await stop
    await asyncio.wait_for(execution_started.wait(), timeout=1)
    release_execution.set()
    await service.drain(asyncio.get_running_loop().time() + 1)

    assert ack["accepted"] is True
    assert stopped_before_registration is False
