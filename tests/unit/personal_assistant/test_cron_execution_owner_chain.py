"""CronExecutionService owns the full accepted-to-awareness lifecycle."""

from __future__ import annotations

import asyncio

import pytest

from personal_assistant.gateway.runtime_delivery.stream import StreamRunOutcome
from personal_assistant.scheduler.cron_execution_service import CronExecutionService
from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore


class _Runner:
    def __init__(self) -> None:
        self.submitted: list[str] = []
        self.awareness: list[str] = []

    async def submit(self, *, job: CronJob) -> tuple[str, str]:
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
            context=None,
            error=None,
        )
        self.failure = failure
        self.calls: list[tuple[str, str, str]] = []

    async def deliver(
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
            context=None,
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
        stream_delivery=delivery,
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
        stream_delivery=_Delivery(failure=RuntimeError("stream broke")),
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
            context=None,
            error=error,
        )
    )
    service = CronExecutionService(
        agent_id="agent-a",
        workspace_root=tmp_path,
        runner=runner,
        stream_delivery=delivery,
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
            context=None,
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
