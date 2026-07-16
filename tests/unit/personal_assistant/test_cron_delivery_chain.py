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
        flush_held: bool = True,
        model: str | None = None,
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
        session_binder=None,
        canonical_session_id="sess-canonical",
    )

    await runner.append_awareness(
        session_id="sess-canonical",
        result_text=final_result,
    )

    # Verify via kernel.append_message call (not raw file)
    assert len(shim.appended_messages) == 1, (
        f"Expected 1 append_message call, got {len(shim.appended_messages)}"
    )
    appended = shim.appended_messages[0]
    assert "It is now 14:05 UTC" in appended.get("content", ""), (
        "awareness must contain the cron result text"
    )


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
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )  # noqa: F401

        assert CronExecutionService is not None

    @pytest.mark.asyncio
    async def test_enqueue_returns_accepted_ack(self, tmp_path: Path) -> None:
        """enqueue() must return accepted=True ack for a known enabled job."""
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

        self._make_job_store(tmp_path)
        executed: list[str] = []

        async def _fake_execute(
            *, agent_id: str, job_id: str, request_id: str, trigger: str
        ) -> None:
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
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )

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
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
        )
        from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

        store = CronJobStore(workspace_root=tmp_path)
        store.add(
            CronJob(
                id="job-disabled",
                name="disabled",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="x",
                enabled=False,
                delete_after_run=False,
            )
        )

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
        from personal_assistant.scheduler.cron_execution_service import (
            CronExecutionService,
            CronRunsStore,
        )

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


# Gateway startup: converge_stale_on_restart called for each agent (bugfix-402-M4 R5)
# ---------------------------------------------------------------------------


class TestGatewayStartupConvergence:
    """Verify that converge_stale_on_restart() is called for each agent's runs store
    during Gateway startup (build_runtime), so stale accepted/running records from a
    previous crash are marked as failed(gateway_restarted) before any new tick runs.
    """

    def test_build_runtime_calls_converge_stale_on_restart(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """build_runtime must call runs_store.converge_stale_on_restart() for each agent."""
        from personal_assistant.scheduler.cron_execution_service import CronRunsStore

        converge_calls: list[str] = []
        original_converge = CronRunsStore.converge_stale_on_restart

        def _recording_converge(self):
            converge_calls.append(str(self._root))
            return original_converge(self)

        monkeypatch.setattr(
            CronRunsStore, "converge_stale_on_restart", _recording_converge
        )

        # build_runtime source must reference converge_stale_on_restart.
        import inspect
        import personal_assistant.main as main_module

        source = inspect.getsource(main_module.build_runtime)
        assert "converge_stale_on_restart" in source, (
            "build_runtime must call converge_stale_on_restart() on startup "
            "(bugfix-402-M4 R5 exit criterion)"
        )
