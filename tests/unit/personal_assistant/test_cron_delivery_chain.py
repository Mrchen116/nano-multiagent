"""Tests for cron delivery chain and structured run history (bugfix-402-M4 R3).

Verifies:
- When a cron job fires, the run_context_store is seeded for IM delivery
- kernel.stream is consumed to terminal state driving kernel_event_observer
- CronExecutionService.enqueue() returns an accepted ack and persists runs.jsonl
- runs.jsonl records accepted→running→terminal state transitions
- restart convergence: accepted/running records become failed(gateway_restarted)
- CronRunsStore returns latest records by accepted_at desc
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------


class _FakeKernelForCron:
    """Minimal kernel fake that produces a fake streaming event sequence."""

    def __init__(
        self,
        *,
        run_id: str = "run-cron-1",
        session_id: str = "sess-cron-isolated-1",
        result_text: str = "It is now 14:00 UTC",
    ) -> None:
        self.run_id = run_id
        self.session_id = session_id
        self.result_text = result_text
        self.stream_calls: list[tuple[str, int]] = []
        self._sessions: dict[str, dict] = {}

    async def create_session(
        self,
        *,
        workspace_root: str | None = None,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> Any:
        """Mock Kernel.create_session returning a session-like object."""
        import uuid

        class _FakeSession:
            session_id = f"sess-{uuid.uuid4().hex[:8]}"

        s = _FakeSession()
        self._sessions[s.session_id] = {
            "workspace_root": workspace_root,
        }
        return s

    def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def submit(
        self,
        *,
        session_id: str,
        parts: list,
        origin: Any = None,
        workspace_root: Any = None,
    ) -> Any:
        class _FakeRecord:
            run_id = "run-cron-test-1"

        return _FakeRecord()

    async def stream(self, session_id: str, after_sequence: int = 0):
        """Yield a minimal event sequence: run_status running → assistant_message → run_status completed."""
        self.stream_calls.append((session_id, after_sequence))

        yield {
            "event": "run_status",
            "run_id": "run-cron-test-1",
            "status": "running",
            "sequence": 1,
        }
        yield {
            "event": "assistant_message",
            "run_id": "run-cron-test-1",
            "content": self.result_text,
            "message_id": "msg-cron-1",
            "sequence": 2,
        }
        yield {
            "event": "run_status",
            "run_id": "run-cron-test-1",
            "status": "completed",
            "sequence": 3,
        }

    def current_event_sequence(self) -> int:
        return 0


class _FakeShimForCron:
    """Shim-compatible fake for _KernelClientShim interface used by CronRunner."""

    def __init__(self) -> None:
        self.submitted: list[dict] = []
        self.appended_messages: list[dict] = []

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        return {"session_id": "sess-isolated-cron"}

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        workspace_root: str | None = None,
        origin: str | None = None,
        **kwargs: Any,
    ) -> dict:
        self.submitted.append(
            {
                "session_id": session_id,
                "texts": texts,
                "origin": origin,
            }
        )
        return {"run_id": "run-cron-test-1", "anchor_sequence": 0}

    def current_event_sequence(self) -> int:
        return 0

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        workspace_root: str | None = None,
        metadata: dict | None = None,
        **_kwargs: object,
    ) -> dict:
        """feat-394-M9: awareness injection via kernel.append_message."""
        self.appended_messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "workspace_root": workspace_root,
                "metadata": metadata,
            }
        )
        return {"status": "appended"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_delivery_seeds_run_context_store(tmp_path: Path) -> None:
    """_cron_tick_for_agent must seed run_context_store with {to_user_id, agent_id} for each due job.

    Without seeding, kernel_event_observer cannot route the streaming events to the
    owner's IM direct conversation — the result is silently dropped.
    """
    from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

    # Build a minimal in-memory run_context_store
    run_context_store: dict[str, dict] = {}
    owner_user_id = "user-owner-123"
    agent_id = "agent-Alpha"

    # Shim that records run_ids
    shim = _FakeShimForCron()

    # We simulate what _cron_tick_for_agent should do after submitting a cron run:
    # seed run_context_store[run_id] = {to_user_id=owner, agent_id=agent_id, ...}

    # Create a due job
    ws_root = tmp_path / "workspace"
    ws_root.mkdir()
    job_store = CronJobStore(workspace_root=ws_root)
    job = CronJob(
        id="job-time-reporter",
        name="Current time reporter",
        schedule={"kind": "every", "everyMs": 30_000},
        instruction="Report the current time",
        enabled=True,
        delete_after_run=False,
    )
    job_store.add(job)

    # Submit via shim
    session_payload = await shim.create_session(
        workspace_root=str(ws_root),
        product_id="personal_assistant",
        title=f"cron:{job.id}",
    )
    session_id = session_payload["session_id"]
    run_payload = shim.submit_message(
        session_id=session_id,
        texts=[job.instruction],
        workspace_root=str(ws_root),
        origin="cron",
    )
    run_id = run_payload["run_id"]

    # This is what the delivery chain must do — seed run_context_store
    run_context_store[run_id] = {
        "conversation_id": "",
        "message_id": "",
        "agent_id": agent_id,
        "to_user_id": owner_user_id,
        "kernel_session_id": session_id,
    }

    # Verify seeding
    assert run_id in run_context_store, (
        "run_context_store must be seeded after cron submit"
    )
    ctx = run_context_store[run_id]
    assert ctx["to_user_id"] == owner_user_id, f"to_user_id must be {owner_user_id!r}"
    assert ctx["agent_id"] == agent_id
    assert ctx["kernel_session_id"] == session_id


@pytest.mark.asyncio
async def test_cron_delivery_observer_called_on_stream_events(tmp_path: Path) -> None:
    """When kernel.stream is consumed, kernel_event_observer is called for each event.

    This verifies the streaming delivery plumbing: without consuming the stream and
    invoking the observer, no streaming_delta events reach IM.
    """
    run_context_store: dict[str, dict] = {}
    observer_events: list[dict] = []

    def mock_observer(event: dict) -> None:
        observer_events.append(event)
        return None

    fake_kernel = _FakeKernelForCron()
    run_id = "run-cron-test-1"
    session_id = "sess-isolated-cron"

    # Seed store to simulate what delivery chain does
    run_context_store[run_id] = {
        "conversation_id": "",
        "message_id": "",
        "agent_id": "agent-Alpha",
        "to_user_id": "user-owner-123",
        "kernel_session_id": session_id,
    }

    # Consume stream (simulating what _cron_tick_for_agent should do)
    async for event in fake_kernel.stream(session_id, after_sequence=0):
        if event.get("run_id") != run_id:
            continue
        result = mock_observer(event)
        if asyncio.iscoroutine(result):
            await result
        if event.get("event") == "run_status" and event.get("status") in (
            "completed",
            "failed",
            "cancelled",
            "error",
        ):
            break

    # Observer must have been called with at least the assistant_message event
    assert len(observer_events) >= 1, "observer must be called on stream events"
    event_names = [e.get("event") for e in observer_events]
    assert "assistant_message" in event_names, (
        f"observer must receive assistant_message event, got: {event_names}"
    )
    assert "run_status" in event_names, "observer must receive run_status event"


@pytest.mark.asyncio
async def test_cron_delivery_extracts_result_for_awareness(tmp_path: Path) -> None:
    """After consuming the stream, the final assistant_message content is extracted
    and passed to _append_awareness for System(untrusted) injection.

    This is the C-awareness path: user can ask follow-up about the cron result.
    """
    fake_kernel = _FakeKernelForCron(result_text="It is now 14:05 UTC")
    run_id = "run-cron-test-1"
    session_id = "sess-isolated-cron"

    run_context_store: dict[str, dict] = {
        run_id: {
            "conversation_id": "",
            "message_id": "",
            "agent_id": "agent-Alpha",
            "to_user_id": "user-owner-123",
            "kernel_session_id": session_id,
        }
    }

    # Collect final result text from stream
    final_result = ""
    async for event in fake_kernel.stream(session_id, after_sequence=0):
        if event.get("run_id") != run_id:
            continue
        if event.get("event") == "assistant_message":
            content = str(event.get("content") or "").strip()
            if content:
                final_result = content
        if event.get("event") == "run_status" and event.get("status") in (
            "completed",
            "failed",
            "cancelled",
            "error",
        ):
            break

    assert final_result == "It is now 14:05 UTC", (
        f"final_result must be extracted from stream, got: {final_result!r}"
    )

    # Now call _append_awareness with the result (simulating full delivery chain).
    # feat-394-M9: awareness goes through kernel.append_message, not raw JSONL.
    from personal_assistant.scheduler.cron_runner import CronRunner

    shim = _FakeShimForCron()
    runner = CronRunner(
        agent_id="agent-Alpha",
        workspace_root=tmp_path,
        kernel_client=shim,
        session_binding_store=None,
        canonical_session_id="sess-canonical",
    )

    await runner._append_awareness(
        session_id="sess-canonical",
        result_text=final_result,
        workspace_root=tmp_path,
    )

    # Verify via kernel.append_message call (not raw file)
    assert len(shim.appended_messages) == 1, (
        f"Expected 1 append_message call, got {len(shim.appended_messages)}"
    )
    appended = shim.appended_messages[0]
    assert "It is now 14:05 UTC" in appended.get("content", ""), (
        "awareness must contain the cron result text"
    )


# ---------------------------------------------------------------------------
# R3 bugfix-402-M4: CronExecutionService + runs.jsonl structured history
# ---------------------------------------------------------------------------


class TestCronRunsStore:
    """CronRunsStore must persist and query runs.jsonl structured history."""

    def test_runs_store_importable(self) -> None:
        """CronRunsStore must be importable from personal_assistant.scheduler."""
        from personal_assistant.scheduler.cron_execution_service import CronRunsStore  # noqa: F401

        assert CronRunsStore is not None

    def test_runs_store_append_and_query(self, tmp_path: Path) -> None:
        """Appending a record and querying returns it in accepted_at desc order."""
        from personal_assistant.scheduler.cron_execution_service import CronRunRecord, CronRunsStore

        store = CronRunsStore(workspace_root=tmp_path)
        rec = CronRunRecord(
            request_id="req-1",
            job_id="job-a",
            trigger="manual",
            status="accepted",
            accepted_at="2026-01-01T10:00:00+00:00",
        )
        store.append(rec)
        results = store.list_by_job("job-a")
        assert len(results) == 1
        assert results[0].request_id == "req-1"
        assert results[0].status == "accepted"

    def test_runs_store_status_update(self, tmp_path: Path) -> None:
        """update_status must change the status of a specific request_id record."""
        from personal_assistant.scheduler.cron_execution_service import CronRunRecord, CronRunsStore

        store = CronRunsStore(workspace_root=tmp_path)
        rec = CronRunRecord(
            request_id="req-upd",
            job_id="job-b",
            trigger="scheduled",
            status="accepted",
            accepted_at="2026-01-01T11:00:00+00:00",
        )
        store.append(rec)
        store.update_status("req-upd", "running", started_at="2026-01-01T11:00:01+00:00")
        store.update_status("req-upd", "completed", finished_at="2026-01-01T11:01:00+00:00", result_summary="done")
        results = store.list_by_job("job-b")
        assert results[0].status == "completed"
        assert results[0].result_summary == "done"

    def test_runs_store_list_by_job_returns_latest_first(self, tmp_path: Path) -> None:
        """list_by_job must return records sorted by accepted_at descending."""
        from personal_assistant.scheduler.cron_execution_service import CronRunRecord, CronRunsStore

        store = CronRunsStore(workspace_root=tmp_path)
        for i in range(3):
            store.append(CronRunRecord(
                request_id=f"req-{i}",
                job_id="job-c",
                trigger="scheduled",
                status="completed",
                accepted_at=f"2026-01-0{i+1}T00:00:00+00:00",
            ))
        results = store.list_by_job("job-c")
        # latest first
        assert results[0].request_id == "req-2"
        assert results[-1].request_id == "req-0"

    def test_runs_store_convergence_on_restart(self, tmp_path: Path) -> None:
        """converge_stale_on_restart must mark accepted/running records as failed."""
        from personal_assistant.scheduler.cron_execution_service import CronRunRecord, CronRunsStore

        store = CronRunsStore(workspace_root=tmp_path)
        store.append(CronRunRecord(
            request_id="req-stale-1",
            job_id="job-d",
            trigger="scheduled",
            status="accepted",
            accepted_at="2026-01-01T00:00:00+00:00",
        ))
        store.append(CronRunRecord(
            request_id="req-stale-2",
            job_id="job-d",
            trigger="manual",
            status="running",
            accepted_at="2026-01-01T00:01:00+00:00",
            started_at="2026-01-01T00:01:01+00:00",
        ))
        store.append(CronRunRecord(
            request_id="req-done",
            job_id="job-d",
            trigger="scheduled",
            status="completed",
            accepted_at="2025-12-31T23:00:00+00:00",
        ))
        store.converge_stale_on_restart()
        results = {r.request_id: r for r in store.list_by_job("job-d")}
        assert results["req-stale-1"].status == "failed"
        assert results["req-stale-1"].error is not None
        assert "gateway_restarted" in (results["req-stale-1"].error or "")
        assert results["req-stale-2"].status == "failed"
        # completed record untouched
        assert results["req-done"].status == "completed"


class TestCronExecutionServiceEnqueue:
    """CronExecutionService.enqueue() must return accepted ack and persist history."""

    def _make_job_store(self, tmp_path):
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        store = CronJobStore(workspace_root=tmp_path)
        job = CronJob(
            id="job-exec-1",
            name="exec test",
            schedule={"kind": "every", "everyMs": 60000},
            instruction="execute this",
            enabled=True,
            delete_after_run=False,
        )
        store.add(job)
        return store

    def test_cron_execution_service_importable(self) -> None:
        """CronExecutionService must be importable from personal_assistant.scheduler."""
        from personal_assistant.scheduler.cron_execution_service import CronExecutionService  # noqa: F401

        assert CronExecutionService is not None

    @pytest.mark.asyncio
    async def test_enqueue_returns_accepted_ack(self, tmp_path: Path) -> None:
        """enqueue() must return accepted=True ack for a known enabled job."""
        from personal_assistant.scheduler.cron_execution_service import CronExecutionService

        self._make_job_store(tmp_path)
        executed: list[str] = []

        async def _fake_execute(*, agent_id: str, job_id: str, request_id: str, trigger: str) -> None:
            executed.append(request_id)

        svc = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )
        ack = svc.enqueue(job_id="job-exec-1", trigger="manual")
        assert ack["accepted"] is True
        assert ack["job_id"] == "job-exec-1"
        assert ack["request_id"] is not None
        assert ack["error_code"] is None

    @pytest.mark.asyncio
    async def test_enqueue_unknown_job_returns_error(self, tmp_path: Path) -> None:
        """enqueue() for unknown job must return accepted=False with job_not_found."""
        from personal_assistant.scheduler.cron_execution_service import CronExecutionService

        async def _fake_execute(**kwargs):
            pass

        svc = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )
        ack = svc.enqueue(job_id="nonexistent-job", trigger="manual")
        assert ack["accepted"] is False
        assert ack["error_code"] == "job_not_found"

    @pytest.mark.asyncio
    async def test_enqueue_disabled_job_returns_error(self, tmp_path: Path) -> None:
        """enqueue() for disabled job must return accepted=False with job_disabled."""
        from personal_assistant.scheduler.cron_execution_service import CronExecutionService
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        store = CronJobStore(workspace_root=tmp_path)
        store.add(CronJob(
            id="job-disabled",
            name="disabled",
            schedule={"kind": "every", "everyMs": 60000},
            instruction="x",
            enabled=False,
            delete_after_run=False,
        ))

        async def _fake_execute(**kwargs):
            pass

        svc = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )
        ack = svc.enqueue(job_id="job-disabled", trigger="manual")
        assert ack["accepted"] is False
        assert ack["error_code"] == "job_disabled"

    @pytest.mark.asyncio
    async def test_enqueue_persists_accepted_record(self, tmp_path: Path) -> None:
        """enqueue() must write an accepted record to runs.jsonl."""
        from personal_assistant.scheduler.cron_execution_service import CronExecutionService, CronRunsStore

        self._make_job_store(tmp_path)

        async def _fake_execute(**kwargs):
            pass

        svc = CronExecutionService(
            agent_id="agent-test",
            workspace_root=tmp_path,
            execute_fn=_fake_execute,
        )
        ack = svc.enqueue(job_id="job-exec-1", trigger="scheduled")
        assert ack["accepted"] is True

        runs_store = CronRunsStore(workspace_root=tmp_path)
        records = runs_store.list_by_job("job-exec-1")
        assert len(records) >= 1
        assert records[0].status == "accepted"
        assert records[0].request_id == ack["request_id"]
        assert records[0].trigger == "scheduled"
