"""Tests for feat-394-M1 B: transcript trimming after silent heartbeat ticks.

B condition: after a silent poll (no meaningful work), the heartbeat runner must
truncate the JSONL session file back to the pre-submit line count, eliminating
the heartbeat trigger prompt and ack turn from the session history (net-zero residual).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig, HeartbeatConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatRunRecord,
    HeartbeatTickSummary,
)


# ---------------------------------------------------------------------------
# B — transcript 修剪：静默轮询后会话无噪声
# ---------------------------------------------------------------------------


def test_polling_runner_has_trim_silent_tick_method(tmp_path: Path) -> None:
    """PollingHeartbeatRunner 必须有 trim_silent_tick 方法."""
    from personal_assistant.main import PollingHeartbeatRunner

    assert hasattr(PollingHeartbeatRunner, "trim_silent_tick"), (
        "PollingHeartbeatRunner 缺少 trim_silent_tick 方法"
    )


def test_polling_runner_trims_silent_tick_truncates_jsonl(tmp_path: Path) -> None:
    """PollingHeartbeatRunner.trim_silent_tick 截断 JSONL 到 pre_submit_line_count 行.

    这是 B 条退出标准的核心：静默轮询完成后，JSONL 文件被截断到 run 之前的行数，
    消除 heartbeat 触发 prompt + ack turn（net zero residual）。
    """
    from personal_assistant.main import PollingHeartbeatRunner

    # 准备一个包含 3 行的 JSONL 文件（模拟 run 前的 session 历史）
    session_dir = tmp_path / ".nanoassistant" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "sess-b1.jsonl"
    pre_submit_lines = [
        '{"type":"session_created","session_id":"sess-b1","created_at":"2026-01-01T00:00:00Z"}\n',
        '{"type":"turn","uuid":"msg-1","role":"user","content":"hello","timestamp":"2026-01-01T00:01:00Z"}\n',
        '{"type":"turn","uuid":"msg-2","role":"assistant","content":"hi there","timestamp":"2026-01-01T00:01:01Z"}\n',
    ]
    session_file.write_text("".join(pre_submit_lines), encoding="utf-8")

    # 模拟 heartbeat run 追加了触发 prompt 和 ack turn（2 行）
    with session_file.open("a", encoding="utf-8") as f:
        f.write(
            '{"type":"turn","uuid":"hb-prompt","role":"user","content":"Read HEARTBEAT.md...","timestamp":"2026-01-01T01:00:00Z"}\n'
        )
        f.write(
            '{"type":"turn","uuid":"hb-ok","role":"assistant","content":"HEARTBEAT_OK","timestamp":"2026-01-01T01:00:01Z"}\n'
        )

    assert session_file.read_text(encoding="utf-8").count("\n") == 5, (
        "setup: should be 5 lines"
    )

    runner = PollingHeartbeatRunner.__new__(PollingHeartbeatRunner)

    # trim_silent_tick(session_file, pre_submit_line_count) 应截断到 pre_submit_line_count 行
    asyncio.run(
        runner.trim_silent_tick(
            session_file=session_file,
            pre_submit_line_count=len(pre_submit_lines),
        )
    )

    remaining = session_file.read_text(encoding="utf-8")
    remaining_lines = [l for l in remaining.splitlines() if l.strip()]
    assert len(remaining_lines) == 3, (
        f"截断后应剩 3 行（run 前的历史）；实际剩 {len(remaining_lines)} 行:\n{remaining}"
    )
    assert "HEARTBEAT_OK" not in remaining, (
        "静默 tick 修剪后 HEARTBEAT_OK ack turn 不应残留"
    )
    assert "HEARTBEAT.md" not in remaining, (
        "静默 tick 修剪后 heartbeat 触发 prompt 不应残留"
    )


class _SingleRunScheduler:
    def __init__(self, record: HeartbeatRunRecord) -> None:
        self._record = record

    async def tick(self) -> HeartbeatTickSummary:
        return HeartbeatTickSummary(
            triggered_runs=(self._record,), skipped_agents=()
        )


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


async def _drive_heartbeat_record(
    *,
    record: HeartbeatRunRecord,
    kernel: _HeartbeatStreamKernel,
    observer_events: list[dict[str, object]],
) -> None:
    from personal_assistant.main import PollingHeartbeatRunner

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
async def test_fast_silent_heartbeat_uses_pre_submit_transcript_baseline(
    tmp_path: Path,
) -> None:
    """A heartbeat that finishes before consumption still removes only its own turns."""

    session_file = tmp_path / ".nanoassistant" / "sessions" / "sess-hb.jsonl"
    session_file.parent.mkdir(parents=True)
    initial = '{"type":"session_created"}\n'
    session_file.write_text(
        initial
        + '{"role":"user","content":"heartbeat"}\n'
        + '{"role":"assistant","content":"HEARTBEAT_OK"}\n',
        encoding="utf-8",
    )
    record = HeartbeatRunRecord(
        agent_id="agent-hb",
        due_at=datetime(2026, 7, 16, tzinfo=UTC),
        run_id="run-hb",
        session_id="sess-hb",
        transcript_baseline=SimpleNamespace(
            session_file=session_file, non_empty_line_count=1
        ),
    )

    await _drive_heartbeat_record(
        record=record,
        kernel=_HeartbeatStreamKernel(session_file=session_file, status="completed"),
        observer_events=[],
    )

    assert session_file.read_text(encoding="utf-8") == initial


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
        transcript_baseline=SimpleNamespace(
            session_file=session_file, non_empty_line_count=1
        ),
    )
    observer_events: list[dict[str, object]] = []

    await _drive_heartbeat_record(
        record=record,
        kernel=_HeartbeatStreamKernel(
            session_file=session_file,
            status=status,
            append_during_stream=True,
        ),
        observer_events=observer_events,
    )

    assert len(session_file.read_text(encoding="utf-8").splitlines()) == 3
    terminal = [
        event for event in observer_events if event.get("event") == "run_terminal_reconcile"
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
