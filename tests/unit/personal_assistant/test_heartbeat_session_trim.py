"""Tests for feat-394-M1 B: transcript trimming after silent heartbeat ticks.

B condition: after a silent poll (no meaningful work), the heartbeat runner must
truncate the JSONL session file back to the pre-submit line count, eliminating
the heartbeat trigger prompt and ack turn from the session history (net-zero residual).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig, HeartbeatConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatRunRecord,
    HeartbeatTickSummary,
)


class _SingleRunScheduler:
    def __init__(self, record: HeartbeatRunRecord) -> None:
        self._record = record

    async def tick(self) -> HeartbeatTickSummary:
        return HeartbeatTickSummary(triggered_runs=(self._record,), skipped_agents=())


class _HeartbeatStreamKernel:
    def __init__(
        self,
        *,
        session_file: Path,
        status: str,
        append_during_stream: bool = False,
    ) -> None:
        self._session_file = session_file
        self._status = status
        self._append_during_stream = append_during_stream
        self.discarded_run_ids: list[str] = []

    async def stream(self, session_id: str, after_sequence: int = 0):
        del session_id, after_sequence
        if self._append_during_stream:
            with self._session_file.open("a", encoding="utf-8") as handle:
                handle.write('{"role":"user","content":"heartbeat"}\n')
                handle.write('{"role":"assistant","content":"partial"}\n')
        yield {"event": "run_status", "run_id": "run-hb", "status": "running"}
        yield {
            "event": "assistant_message",
            "run_id": "run-hb",
            "content": "HEARTBEAT_OK" if self._status == "completed" else "partial",
        }
        yield {
            "event": "run_status",
            "run_id": "run-hb",
            "status": self._status,
            "error": "heartbeat failed" if self._status == "failed" else None,
        }

    async def discard_run_messages(self, run_id: str) -> bool:
        self.discarded_run_ids.append(run_id)
        return True


async def _drive_heartbeat_record(
    *,
    record: HeartbeatRunRecord,
    kernel: _HeartbeatStreamKernel,
    observer_events: list[dict[str, object]],
) -> None:
    from personal_assistant.scheduler.heartbeat_runner import PollingHeartbeatRunner

    consumed = asyncio.Event()
    agent = AgentWorkspaceConfig(
        agent_id="agent-hb",
        workspace_root=kernel._session_file.parent.parent.parent,  # noqa: SLF001
        features={"cron_scheduling": True},
    )

    async def _mark_after_heartbeat(_agent_id: str) -> None:
        consumed.set()

    def _observe(event: dict[str, object]) -> None:
        observer_events.append(dict(event))

    runner = PollingHeartbeatRunner(
        scheduler=_SingleRunScheduler(record),
        config=HeartbeatConfig(tick_interval_seconds=60),
        kernel=kernel,
        run_context_store={},
        owner_user_id="owner-1",
        kernel_event_observer=_observe,
        cron_tick_fn=_mark_after_heartbeat,
        agent_catalog=LiveAgentCatalog((agent,)),
    )
    await runner.start()
    await asyncio.wait_for(consumed.wait(), timeout=1)
    runner.request_stop()
    await runner.close()


@pytest.mark.asyncio
async def test_fast_silent_heartbeat_delegates_cleanup_by_run_identity(
    tmp_path: Path,
) -> None:
    """A heartbeat that finishes before consumption still removes only its own turns."""

    session_file = tmp_path / ".nanoassistant" / "sessions" / "sess-hb.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text('{"type":"session_created"}\n', encoding="utf-8")
    record = HeartbeatRunRecord(
        agent_id="agent-hb",
        due_at=datetime(2026, 7, 16, tzinfo=UTC),
        run_id="run-hb",
        session_id="sess-hb",
    )

    kernel = _HeartbeatStreamKernel(session_file=session_file, status="completed")

    await _drive_heartbeat_record(
        record=record,
        kernel=kernel,
        observer_events=[],
    )

    assert kernel.discarded_run_ids == ["run-hb"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "cancelled"])
async def test_non_success_heartbeat_preserves_transcript_and_emits_failed_terminal(
    tmp_path: Path, status: str
) -> None:
    """Failed/cancelled heartbeat work must never take the silent-success trim path."""

    session_file = tmp_path / ".nanoassistant" / "sessions" / "sess-hb.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text('{"type":"session_created"}\n', encoding="utf-8")
    record = HeartbeatRunRecord(
        agent_id="agent-hb",
        due_at=datetime(2026, 7, 16, tzinfo=UTC),
        run_id="run-hb",
        session_id="sess-hb",
    )
    observer_events: list[dict[str, object]] = []
    kernel = _HeartbeatStreamKernel(
        session_file=session_file,
        status=status,
        append_during_stream=True,
    )

    await _drive_heartbeat_record(
        record=record,
        kernel=kernel,
        observer_events=observer_events,
    )

    assert len(session_file.read_text(encoding="utf-8").splitlines()) == 3
    assert kernel.discarded_run_ids == []
    terminal = [
        event
        for event in observer_events
        if event.get("event") == "run_terminal_reconcile"
    ]
    assert terminal == [
        {
            "event": "run_terminal_reconcile",
            "run_id": "run-hb",
            "reason": "heartbeat failed" if status == "failed" else "cancelled",
            "finalize_bubble": True,
            "delivery_status": "failed",
        }
    ]
