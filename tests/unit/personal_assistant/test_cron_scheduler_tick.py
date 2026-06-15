"""Unit tests for CronScheduler tick behavior (multi-job, submit_fn integration).

Covers:
- Tick submits due jobs via submit_fn
- Tick skips disabled jobs
- Tick respects cron_enabled gate (agent not enabled → no tick)
- delete_after_run: one-shot at job removed after execution
- Integration smoke: cron/at schedule types wired through CronScheduler
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

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


# ---------------------------------------------------------------------------
# Integration smoke: cron and at schedule types wired through CronScheduler
# (timing semantics are authoritative in test_schedule_primitives.py)
# ---------------------------------------------------------------------------


class TestCronAtSchedulerSmoke:
    def test_cron_fires_when_matching_minute(self, tmp_path: Path) -> None:
        """Smoke: cron expression job is returned by _compute_due_jobs on matching minute."""
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(job_id="j1", schedule={"kind": "cron", "expr": "0 9 * * *"})
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert len(due) == 1

    def test_at_fires_when_time_arrived(self, tmp_path: Path) -> None:
        """Smoke: at job is returned by _compute_due_jobs when now == due_at."""
        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            _make_job(
                job_id="j1",
                schedule={"kind": "at", "at": "2026-01-01T10:00:00Z"},
                delete_after_run=True,
            )
        )
        state_store = CronSchedulerStateStore(state_path=tmp_path / "cron-state.json")
        scheduler = CronScheduler(
            agent_id="agent-1", job_store=store, state_store=state_store, submit_fn=None
        )
        now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        due = scheduler._compute_due_jobs(now=now)
        assert len(due) == 1


# refactor-406-M1 R7: TestGatewayCronDispatcher (the HostCapabilityDispatcher bridge:
# importable / is_host_capability_dispatcher / invoke-enqueue routing) deleted — the
# bridge is removed (决策 9). Cron manual-run enqueue routing now lives in the closure
# cron tool and is covered by test_cron_tool_closure.py (roundtrip / per-agent routing /
# missing-service ack). No behavior lost; these tested eliminated implementation.


class TestCronExecutionServiceDrain:
    """Verify that CronExecutionService.drain() awaits tracked pending tasks.

    bugfix-402-M6 W-1: enqueue() must track create_task() handles and drain()
    must gather them before the caller proceeds to tear down the IM transport.
    """

    @pytest.mark.asyncio
    async def test_drain_awaits_pending_tasks(self, tmp_path: Path) -> None:
        """drain() must complete only after all tracked execute_fn tasks finish."""
        import asyncio

        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        finished: list[str] = []

        async def slow_execute(
            *, agent_id: str, job_id: str, request_id: str, trigger: str
        ) -> None:
            await asyncio.sleep(0.05)
            finished.append(job_id)

        service = CronExecutionService(
            agent_id="agent-drain",
            workspace_root=tmp_path,
            execute_fn=slow_execute,
        )
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(
            CronJob(
                id="job-drain-1",
                name="Drain Test",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="drain test",
            )
        )

        service.enqueue(job_id="job-drain-1", trigger="manual")
        assert len(finished) == 0, "task must not have finished before drain()"

        await service.drain(timeout=5.0)
        assert "job-drain-1" in finished, "drain() must await tracked execute_fn task"

    @pytest.mark.asyncio
    async def test_drain_no_tasks_returns_immediately(self, tmp_path: Path) -> None:
        """drain() with no pending tasks must return without hanging."""
        import asyncio

        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

        service = CronExecutionService(
            agent_id="agent-drain-empty",
            workspace_root=tmp_path,
            execute_fn=AsyncMock(),
        )
        # Should return before timeout.
        await asyncio.wait_for(service.drain(timeout=1.0), timeout=2.0)

    @pytest.mark.asyncio
    async def test_drain_does_not_miss_context_b_task(self, tmp_path: Path) -> None:
        """drain() must not return before a Context B task (call_soon_threadsafe path) completes.

        bugfix-402 code-review: enqueue() via asyncio.to_thread calls
        call_soon_threadsafe; the Task is created on the loop inside the callback.
        Without the pending_count gate, drain() could snapshot _pending_tasks before
        _schedule_with_tracking fires and return while the task is still in-flight.
        """
        import asyncio
        import threading

        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        finished: list[str] = []

        async def slow_execute(
            *, agent_id: str, job_id: str, request_id: str, trigger: str
        ) -> None:
            await asyncio.sleep(0.05)
            finished.append(job_id)

        loop = asyncio.get_running_loop()
        service = CronExecutionService(
            agent_id="agent-ctxb-drain",
            workspace_root=tmp_path,
            execute_fn=slow_execute,
            # Inject the running loop so enqueue() enters Context B
            # (non-running-loop thread path) when called via asyncio.to_thread.
            gateway_loop=loop,
        )
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(
            CronJob(
                id="job-ctxb-1",
                name="Context B Drain Test",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="ctx b drain test",
            )
        )

        # Call enqueue from a worker thread (simulates asyncio.to_thread path).
        # In that thread there is no running loop, so enqueue takes the Context B
        # branch (call_soon_threadsafe) — the Task is not yet in _pending_tasks
        # when enqueue() returns to the thread.
        enqueue_done = threading.Event()

        def _enqueue_in_thread() -> None:
            service.enqueue(job_id="job-ctxb-1", trigger="manual")
            enqueue_done.set()

        thread = threading.Thread(target=_enqueue_in_thread, daemon=True)
        thread.start()

        # Yield to allow the thread to call enqueue() and the loop to dispatch
        # the call_soon_threadsafe callback before drain() runs.
        enqueue_done.wait(timeout=2.0)

        assert len(finished) == 0, "task must not have finished before drain()"

        await service.drain(timeout=5.0)
        assert "job-ctxb-1" in finished, (
            "drain() must wait for Context B task registered via call_soon_threadsafe"
        )


class TestGatewayCronDispatcherDrainAll:
    """Verify that CronServiceRegistry.drain_all() drains all registered services.

    bugfix-402-M6 W-1: drain_all() is called after kernel.aclose() and before
    im_connection_manager.close() in GatewayRuntime._run_until_shutdown().
    refactor-406-M1 R7: lifecycle moved from GatewayCronDispatcher to
    CronServiceRegistry (the bridge is gone; the registry keeps register/
    set_gateway_loop/drain_all).
    """

    @pytest.mark.asyncio
    async def test_drain_all_drains_all_services(self, tmp_path: Path) -> None:
        """drain_all() must call drain() on each unique registered service."""
        import asyncio

        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore
        from personal_assistant.scheduler.cron_service_registry import (
            CronServiceRegistry,
        )

        finished: list[str] = []

        async def make_slow_execute(label: str):
            async def _exec(
                *, agent_id: str, job_id: str, request_id: str, trigger: str
            ) -> None:
                await asyncio.sleep(0.05)
                finished.append(label)

            return _exec

        ws1 = tmp_path / "agent1"
        ws1.mkdir()
        ws2 = tmp_path / "agent2"
        ws2.mkdir()

        svc1 = CronExecutionService(
            agent_id="agent-1",
            workspace_root=ws1,
            execute_fn=await make_slow_execute("svc1"),
        )
        svc2 = CronExecutionService(
            agent_id="agent-2",
            workspace_root=ws2,
            execute_fn=await make_slow_execute("svc2"),
        )

        for ws, svc, label in [(ws1, svc1, "job-a1"), (ws2, svc2, "job-a2")]:
            store = CronJobStore(workspace_root=ws)
            store.add(
                CronJob(
                    id=label,
                    name=label,
                    schedule={"kind": "every", "everyMs": 60000},
                    instruction="test",
                )
            )
            svc.enqueue(job_id=label, trigger="manual")

        dispatcher = CronServiceRegistry()
        # bugfix-402 round-2: register by agent_id (not workspace_root).
        dispatcher.register("agent-1", svc1)
        dispatcher.register("agent-2", svc2)

        assert len(finished) == 0
        await dispatcher.drain_all(timeout=5.0)
        assert "svc1" in finished and "svc2" in finished

    @pytest.mark.asyncio
    async def test_drain_all_deduplicates_same_service_under_two_keys(
        self, tmp_path: Path
    ) -> None:
        """drain_all() must not drain the same service twice when registered under two keys."""
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_service_registry import (
            CronServiceRegistry,
        )

        drain_count = 0

        service = CronExecutionService(
            agent_id="agent-dedup",
            workspace_root=tmp_path,
            execute_fn=AsyncMock(),
        )

        async def _count_drain(timeout: float = 30.0) -> None:
            nonlocal drain_count
            drain_count += 1

        service.drain = _count_drain  # type: ignore[method-assign]

        dispatcher = CronServiceRegistry()
        # Same service registered under two agent_ids — drain must dedup by identity.
        dispatcher.register("agent-dedup", service)
        dispatcher.register("agent-dedup-alias", service)
        await dispatcher.drain_all()
        assert drain_count == 1, (
            "drain_all() must deduplicate and call drain() exactly once"
        )
