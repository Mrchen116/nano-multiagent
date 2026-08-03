"""Cron admission history and Gateway-startup convergence behavior."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestCronExecutionServiceEnqueue:
    """CronExecutionService.enqueue() must return an ack and persist history."""

    def _make_job_store(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            CronJob(
                id="job-exec-1",
                name="exec test",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="execute this",
                enabled=True,
                delete_after_run=False,
            )
        )

    @pytest.mark.asyncio
    async def test_enqueue_returns_accepted_ack(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

        self._make_job_store(tmp_path)

        async def _fake_execute(**_kwargs: object) -> None:
            return None

        service = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )

        ack = service.enqueue(job_id="job-exec-1", trigger="manual")

        assert ack["accepted"] is True
        assert ack["job_id"] == "job-exec-1"
        assert ack["request_id"]
        assert ack["error_code"] is None

    @pytest.mark.asyncio
    async def test_enqueue_unknown_job_returns_error(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

        async def _fake_execute(**_kwargs: object) -> None:
            return None

        service = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )

        ack = service.enqueue(job_id="nonexistent-job", trigger="manual")

        assert ack["accepted"] is False
        assert ack["error_code"] == "job_not_found"

    @pytest.mark.asyncio
    async def test_enqueue_disabled_job_returns_error(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        CronJobStore(workspace_root=tmp_path).add(
            CronJob(
                id="job-disabled",
                name="disabled",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="x",
                enabled=False,
                delete_after_run=False,
            )
        )

        async def _fake_execute(**_kwargs: object) -> None:
            return None

        service = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )

        ack = service.enqueue(job_id="job-disabled", trigger="manual")

        assert ack["accepted"] is False
        assert ack["error_code"] == "job_disabled"

    @pytest.mark.asyncio
    async def test_enqueue_persists_accepted_record(self, tmp_path: Path) -> None:
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
            CronRunsStore,
        )

        self._make_job_store(tmp_path)

        async def _fake_execute(**_kwargs: object) -> None:
            return None

        service = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )

        ack = service.enqueue(job_id="job-exec-1", trigger="scheduled")
        records = CronRunsStore(workspace_root=tmp_path).list_by_job("job-exec-1")

        assert len(records) >= 1
        assert records[0].status == "accepted"
        assert records[0].request_id == ack["request_id"]
        assert records[0].trigger == "scheduled"


class TestGatewayStartupConvergence:
    """Converge stale cron runs only after the Gateway enters startup."""

    def test_runtime_converges_stale_runs_after_entering_startup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from personal_assistant.gateway.composition import compose_gateway
        from personal_assistant.scheduler.cron_execution_service import CronRunsStore

        from ._gateway_runtime_test_utils import run_in_thread
        from ._main_helpers import make_minimal_config

        converge_calls: list[str] = []
        original_converge = CronRunsStore.converge_stale_on_restart

        def _recording_converge(self: CronRunsStore) -> int:
            converge_calls.append(str(self._root))  # noqa: SLF001
            return original_converge(self)

        monkeypatch.setattr(
            CronRunsStore, "converge_stale_on_restart", _recording_converge
        )

        runtime = compose_gateway(make_minimal_config(tmp_path))
        assert converge_calls == []

        thread, outcome = run_in_thread(runtime)
        try:
            assert runtime.wait_until_ready(timeout=2.0) is True
        finally:
            runtime.request_shutdown()
            thread.join(timeout=5.0)

        assert outcome.get("exit_code") == 0
        assert converge_calls == [str((tmp_path / "agent-a").resolve())]
