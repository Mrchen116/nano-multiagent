"""CronExecutionService owns the full accepted-to-awareness lifecycle."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from personal_assistant.gateway.runtime_delivery.stream import StreamRunOutcome
from personal_assistant.scheduler.cron_execution_service import CronExecutionService
from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_scheduler import (
    CronJob,
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("submit_fails", [False, True])
async def test_delete_after_run_waits_for_kernel_submission(
    tmp_path, submit_fails
) -> None:
    store = CronJobStore(workspace_root=tmp_path)
    now = datetime(2026, 9, 10, tzinfo=UTC)
    store.add(
        CronJob(
            id="one-shot",
            name="One shot",
            schedule={"kind": "at", "at": now.isoformat()},
            instruction="run once",
            delete_after_run=True,
        )
    )
    kernel = SimpleNamespace(
        create_session=AsyncMock(return_value={"session_id": "cron-session"}),
        submit_message=Mock(
            return_value={"run_id": "cron-run"},
            side_effect=RuntimeError("submission failed") if submit_fails else None,
        ),
    )
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=CronRunner(
            agent_id="agent-a",
            workspace_root=tmp_path,
            kernel_client=kernel,
            session_binder=None,
        ),
        terminal_consumer=_Delivery(),
    )

    async def enqueue(*, agent_id, job):
        assert service.enqueue(job_id=job.id, trigger="scheduled")["accepted"]

    scheduler = CronScheduler(
        agent_id="agent-a",
        job_store=store,
        state_store=CronSchedulerStateStore(state_path=tmp_path / "state.json"),
        submit_fn=enqueue,
    )
    await scheduler.tick(now=now)
    assert store.get("one-shot") is not None
    await scheduler.tick(now=now)
    await service.drain(asyncio.get_running_loop().time() + 2)
    records = service.runs_store.list_by_job("one-shot")
    assert len(records) == 1
    assert records[0].status == ("failed" if submit_fails else "completed")
    assert records[0].error == ("submit_failed" if submit_fails else None)
    assert (store.get("one-shot") is not None) == submit_fails


class _Runner:
    def __init__(self) -> None:
        self.submitted: list[str] = []
        self.awareness: list[str] = []

    async def submit(
        self, *, job: CronJob, request_id=None, trigger=None
    ) -> tuple[str, str]:
        self.submitted.append(job.id)
        return "run-1", "session-isolated"

    async def append_awareness(self, *, result_text: str) -> bool:
        self.awareness.append(result_text)
        return True


class _Delivery:
    def __init__(
        self,
        *,
        outcome: StreamRunOutcome | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.outcome = outcome or StreamRunOutcome(
            status="completed",
            final_text="cron result",
            delivery=None,
            error=None,
        )
        self.failure = failure
        self.calls: list[tuple[str, str, str]] = []

    async def consume(
        self, *, run_id: str, kernel_session_id: str, agent_id: str
    ) -> StreamRunOutcome:
        self.calls.append((run_id, kernel_session_id, agent_id))
        if self.failure is not None:
            raise self.failure
        return self.outcome


class _TerminalConsumer:
    def __init__(
        self,
        *,
        outcome: StreamRunOutcome | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.outcome = outcome or StreamRunOutcome(
            status="completed",
            final_text="cron result",
            delivery=None,
            error=None,
        )
        self.failure = failure
        self.calls: list[tuple[str, str, str]] = []

    async def consume(
        self, *, run_id: str, kernel_session_id: str, agent_id: str
    ) -> StreamRunOutcome:
        self.calls.append((run_id, kernel_session_id, agent_id))
        if self.failure is not None:
            raise self.failure
        return self.outcome


def _seed_job(tmp_path) -> None:
    CronJobStore(workspace_root=tmp_path).add(
        CronJob(
            id="job-1",
            name="owned lifecycle",
            schedule={"kind": "every", "everyMs": 60_000},
            instruction="run it",
        )
    )


@pytest.mark.asyncio
async def test_service_owns_submit_delivery_terminal_and_awareness(tmp_path) -> None:
    _seed_job(tmp_path)
    runner = _Runner()
    delivery = _Delivery()
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=runner,
        terminal_consumer=delivery,
    )

    ack = service.enqueue(job_id="job-1", trigger="manual")
    await service.drain(asyncio.get_running_loop().time() + 2)

    assert runner.submitted == ["job-1"]
    assert delivery.calls == [("run-1", "session-isolated", "agent-a")]
    assert runner.awareness == ["cron result"]
    record = service.runs_store.list_by_job("job-1")[0]
    assert record.request_id == ack["request_id"]
    assert record.status == "completed"
    assert record.kernel_run_id == "run-1"
    assert record.result_summary == "cron result"


@pytest.mark.asyncio
async def test_service_records_stream_failure_without_awareness(tmp_path) -> None:
    _seed_job(tmp_path)
    runner = _Runner()
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=runner,
        terminal_consumer=_Delivery(failure=RuntimeError("stream broke")),
    )

    ack = service.enqueue(job_id="job-1", trigger="scheduled")
    await service.drain(asyncio.get_running_loop().time() + 2)

    record = service.runs_store.list_by_job("job-1")[0]
    assert record.request_id == ack["request_id"]
    assert record.status == "failed"
    assert record.error == "stream_failed"
    assert runner.awareness == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [
        ("failed", "upstream failed"),
        ("cancelled", "owner cancelled"),
    ],
)
async def test_service_preserves_non_success_terminal_outcome_without_awareness(
    tmp_path, status: str, error: str
) -> None:
    _seed_job(tmp_path)
    runner = _Runner()
    delivery = _Delivery(
        outcome=StreamRunOutcome(
            status=status,
            final_text="partial cron result",
            delivery=None,
            error=error,
        )
    )
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=runner,
        terminal_consumer=delivery,
    )

    ack = service.enqueue(job_id="job-1", trigger="scheduled")
    await service.drain(asyncio.get_running_loop().time() + 2)

    record = service.runs_store.list_by_job("job-1")[0]
    assert record.request_id == ack["request_id"]
    assert record.status == status
    assert record.result_summary == "partial cron result"
    assert record.error == error
    assert runner.awareness == []


def test_service_requires_terminal_consumer_when_runner_owns_submission(
    tmp_path,
) -> None:
    """Optional IM delivery must not make Kernel terminal consumption optional."""

    with pytest.raises(ValueError, match="terminal consumer"):
        CronExecutionService(
            agent_id="agent-a",
            workspace_root=tmp_path,
            runner=_Runner(),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error", "expected_awareness"),
    [
        ("completed", None, ["cron result"]),
        ("failed", "upstream failed", []),
        ("cancelled", "owner cancelled", []),
    ],
)
async def test_no_delivery_configuration_persists_real_terminal_outcome(
    tmp_path,
    status: str,
    error: str | None,
    expected_awareness: list[str],
) -> None:
    """A cron without an IM observer still waits for its mandatory terminal owner."""

    _seed_job(tmp_path)
    runner = _Runner()
    consumer = _TerminalConsumer(
        outcome=StreamRunOutcome(
            status=status,
            final_text="cron result",
            delivery=None,
            error=error,
        )
    )
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=runner,
        terminal_consumer=consumer,
    )

    ack = service.enqueue(job_id="job-1", trigger="scheduled")
    await service.drain(asyncio.get_running_loop().time() + 2)

    record = service.runs_store.list_by_job("job-1")[0]
    assert record.request_id == ack["request_id"]
    assert record.status == status
    assert record.error == error
    assert runner.awareness == expected_awareness
    assert consumer.calls == [("run-1", "session-isolated", "agent-a")]


@pytest.mark.asyncio
async def test_no_delivery_missing_terminal_is_failed_not_completed(tmp_path) -> None:
    """A stream ending before terminal must persist failure in no-delivery mode."""

    _seed_job(tmp_path)
    runner = _Runner()
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=runner,
        terminal_consumer=_TerminalConsumer(
            failure=RuntimeError("stream ended without terminal run_status")
        ),
    )

    ack = service.enqueue(job_id="job-1", trigger="manual")
    await service.drain(asyncio.get_running_loop().time() + 2)

    record = service.runs_store.list_by_job("job-1")[0]
    assert record.request_id == ack["request_id"]
    assert record.status == "failed"
    assert record.error == "stream_failed"
    assert runner.awareness == []
