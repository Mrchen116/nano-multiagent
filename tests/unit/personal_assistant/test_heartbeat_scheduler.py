from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


class _FakeKernelClient:
    def __init__(self) -> None:
        self.created_sessions: list[dict[str, object]] = []
        self.sent_messages: list[dict[str, object]] = []
        self._session_counter = 0
        self._run_counter = 0

    def create_session(self, *, workspace_root: str, product_id: str, title: str | None = None) -> dict[str, object]:
        self._session_counter += 1
        payload = {
            "session_id": f"sess-{self._session_counter}",
            "workspace_root": workspace_root,
            "product_id": product_id,
            "title": title,
        }
        self.created_sessions.append(payload)
        return payload

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self._run_counter += 1
        payload = {
            "run_id": f"run-{self._run_counter}",
            "session_id": session_id,
            "text": text,
        }
        self.sent_messages.append(payload)
        return payload


def _agent(tmp_path: Path, name: str = "agent-a") -> AgentWorkspaceConfig:
    workspace_root = tmp_path / name
    workspace_root.mkdir(parents=True, exist_ok=True)
    return AgentWorkspaceConfig(agent_id=name, workspace_root=workspace_root, title=f"Title for {name}")


def _write_heartbeat(workspace_root: Path, content: str) -> Path:
    path = workspace_root / "HEARTBEAT.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_scheduler_skips_quietly_when_heartbeat_has_no_actionable_task(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(agent.workspace_root, "# Heartbeat\n\n<!-- comment only -->\n")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    summary = scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))

    assert summary.triggered_runs == ()
    assert summary.skipped_agents == (agent.agent_id,)
    assert kernel.created_sessions == []
    assert kernel.sent_messages == []


def test_scheduler_runs_interval_schedule_and_persists_last_due(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ninterval: 30m\n\n- Check inbox status\n",
    )
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(agents=(agent,), kernel_client=kernel, state_store=state_store)

    first = scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))
    second = scheduler.tick(now=datetime(2026, 3, 11, 9, 10, tzinfo=UTC))
    third = scheduler.tick(now=datetime(2026, 3, 11, 9, 30, tzinfo=UTC))

    assert len(first.triggered_runs) == 1
    assert second.triggered_runs == ()
    assert len(third.triggered_runs) == 1
    assert len(kernel.sent_messages) == 2
    assert state_store.load().agents[agent.agent_id].last_due_at == "2026-03-11T09:30:00+00:00"


def test_scheduler_runs_at_schedule_only_once_even_across_restart(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\nat: 2026-03-11T09:00:00+00:00\n\n- Submit daily digest\n",
    )
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    kernel = _FakeKernelClient()

    scheduler = HeartbeatScheduler(agents=(agent,), kernel_client=kernel, state_store=state_store)
    first = scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))

    restarted = HeartbeatScheduler(agents=(agent,), kernel_client=kernel, state_store=state_store)
    second = restarted.tick(now=datetime(2026, 3, 11, 10, 0, tzinfo=UTC))

    assert len(first.triggered_runs) == 1
    assert second.triggered_runs == ()
    assert len(kernel.sent_messages) == 1


def test_scheduler_runs_cron_schedule_on_matching_minute(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ncron: 0 9 * * 1-5\n\n- Start workday review\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    before = scheduler.tick(now=datetime(2026, 3, 11, 8, 59, tzinfo=UTC))
    due = scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))

    assert before.triggered_runs == ()
    assert len(due.triggered_runs) == 1
    assert len(kernel.sent_messages) == 1


def test_scheduler_catches_up_missed_interval_run_after_restart(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ninterval: 30m\n\n- Follow up on outstanding tasks\n",
    )
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    first_kernel = _FakeKernelClient()
    first_scheduler = HeartbeatScheduler(agents=(agent,), kernel_client=first_kernel, state_store=state_store)

    first = first_scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))
    assert len(first.triggered_runs) == 1

    second_kernel = _FakeKernelClient()
    restarted = HeartbeatScheduler(agents=(agent,), kernel_client=second_kernel, state_store=state_store)
    catch_up = restarted.tick(now=datetime(2026, 3, 11, 10, 31, tzinfo=UTC))

    assert [run.due_at.isoformat() for run in catch_up.triggered_runs] == [
        "2026-03-11T09:30:00+00:00",
        "2026-03-11T10:00:00+00:00",
        "2026-03-11T10:30:00+00:00",
    ]
    assert len(second_kernel.sent_messages) == 3


def test_scheduler_rejects_multiple_schedule_modes_in_one_heartbeat(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ninterval: 30m\ncron: 0 9 * * *\n\n- invalid\n",
    )
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=_FakeKernelClient(),
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    with pytest.raises(ValueError, match="exactly one schedule mode"):
        scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))
