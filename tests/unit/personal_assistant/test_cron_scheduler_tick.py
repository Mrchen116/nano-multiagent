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


# GatewayCronDispatcher: HostCapabilityDispatcher implementation (bugfix-402-M4 R4)
# ---------------------------------------------------------------------------


class TestGatewayCronDispatcher:
    """Verify that GatewayCronDispatcher implements the HostCapabilityDispatcher protocol
    and delegates to CronExecutionService.enqueue()."""

    def test_gateway_cron_dispatcher_importable(self) -> None:
        """GatewayCronDispatcher must be importable from personal_assistant."""
        from personal_assistant.scheduler.gateway_cron_dispatcher import (  # noqa: F401
            GatewayCronDispatcher,
        )

    def test_gateway_cron_dispatcher_is_host_capability_dispatcher(self) -> None:
        """GatewayCronDispatcher must subclass HostCapabilityDispatcher."""
        from agent.sdk import HostCapabilityDispatcher
        from personal_assistant.scheduler.gateway_cron_dispatcher import (
            GatewayCronDispatcher,
        )

        assert issubclass(GatewayCronDispatcher, HostCapabilityDispatcher)

    def test_dispatcher_invoke_enqueue_delegates_to_service(
        self, tmp_path: Path
    ) -> None:
        """invoke('personal_assistant.cron.enqueue', ...) must call service.enqueue()."""
        from agent.sdk import HostCapabilityContext
        from personal_assistant.scheduler.gateway_cron_dispatcher import (
            GatewayCronDispatcher,
        )
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob

        calls: list[dict] = []

        async def _noop_execute(**kwargs) -> None:
            pass

        service = CronExecutionService(
            agent_id="agent-1",
            workspace_root=tmp_path,
            execute_fn=_noop_execute,
        )
        # Seed a job so enqueue() does not return job_not_found.
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(CronJob(
            id="job-manual-1",
            name="Manual Test",
            schedule={"kind": "every", "everyMs": 60000},
            instruction="test",
        ))

        original_enqueue = service.enqueue

        def _recording_enqueue(**kwargs):
            calls.append(kwargs)
            return original_enqueue(**kwargs)

        service.enqueue = _recording_enqueue  # type: ignore[method-assign]

        dispatcher = GatewayCronDispatcher(service=service)
        cap_ctx = HostCapabilityContext(
            session_id="sess-1",
            workspace_root=str(tmp_path),
            product_id="personal_assistant",
        )
        result = dispatcher.invoke(
            "personal_assistant.cron.enqueue",
            {"job_id": "job-manual-1"},
            cap_ctx,
        )
        assert len(calls) == 1
        assert calls[0]["job_id"] == "job-manual-1"
        assert calls[0]["trigger"] == "manual"
        assert result.get("accepted") is True

    def test_dispatcher_invoke_unknown_capability_raises(self, tmp_path: Path) -> None:
        """invoke() with unknown capability name must raise ValueError."""
        from agent.sdk import HostCapabilityContext
        from personal_assistant.scheduler.gateway_cron_dispatcher import (
            GatewayCronDispatcher,
        )
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

        async def _noop_execute(**kwargs) -> None:
            pass

        service = CronExecutionService(
            agent_id="agent-1",
            workspace_root=tmp_path,
            execute_fn=_noop_execute,
        )
        dispatcher = GatewayCronDispatcher(service=service)
        cap_ctx = HostCapabilityContext(
            session_id="sess-1",
            workspace_root=str(tmp_path),
            product_id="personal_assistant",
        )
        import pytest as _pytest

        with _pytest.raises((ValueError, NotImplementedError, KeyError)):
            dispatcher.invoke("unknown.capability", {}, cap_ctx)

    def test_dispatcher_propagates_job_not_found_ack(self, tmp_path: Path) -> None:
        """When service.enqueue returns job_not_found, result must carry accepted=False."""
        from agent.sdk import HostCapabilityContext
        from personal_assistant.scheduler.gateway_cron_dispatcher import (
            GatewayCronDispatcher,
        )
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

        async def _noop_execute(**kwargs) -> None:
            pass

        service = CronExecutionService(
            agent_id="agent-1",
            workspace_root=tmp_path,
            execute_fn=_noop_execute,
        )
        # No job added — enqueue should return job_not_found.
        dispatcher = GatewayCronDispatcher(service=service)
        cap_ctx = HostCapabilityContext(
            session_id="sess-1",
            workspace_root=str(tmp_path),
            product_id="personal_assistant",
        )
        result = dispatcher.invoke(
            "personal_assistant.cron.enqueue",
            {"job_id": "nonexistent-job"},
            cap_ctx,
        )
        assert result.get("accepted") is False
        assert result.get("error_code") == "job_not_found"
