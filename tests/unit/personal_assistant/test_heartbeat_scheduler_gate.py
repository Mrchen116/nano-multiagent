from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


class _FakeKernelClient:
    """Sync fake client — used by gate/busy-skip tests."""

    def __init__(self) -> None:
        self.created_sessions: list[dict[str, object]] = []
        self.sent_messages: list[dict[str, object]] = []
        self._session_counter = 0
        self._run_counter = 0

    async def create_session(
        self, *, workspace_root: str, product_id: str, title: str | None = None
    ) -> dict[str, object]:
        self._session_counter += 1
        payload = {
            "session_id": f"sess-{self._session_counter}",
            "workspace_root": workspace_root,
            "product_id": product_id,
            "title": title,
        }
        self.created_sessions.append(payload)
        return payload

    def current_event_sequence(self) -> int:
        return 0

    def submit_message(
        self, *, session_id: str, texts: list[str], **kwargs: object
    ) -> dict[str, object]:
        self._run_counter += 1
        payload: dict[str, object] = {
            "run_id": f"run-{self._run_counter}",
            "session_id": session_id,
            "texts": texts,
            "anchor_sequence": 1,
            "injected": False,
            "status": "queued",
            **kwargs,
        }
        self.sent_messages.append(payload)
        return payload


def _write_heartbeat(workspace_root: Path, content: str) -> Path:
    path = workspace_root / "HEARTBEAT.md"
    path.write_text(content, encoding="utf-8")
    return path


def _agent_with_heartbeat(
    tmp_path: Path, name: str = "agent-a", *, heartbeat_enabled: bool = True
) -> AgentWorkspaceConfig:
    """Create an agent fixture with explicit heartbeat enable state via features dict.

    M9: heartbeat_enabled param maps to features["heartbeat"] (not a direct field).
    """
    workspace_root = tmp_path / name
    workspace_root.mkdir(parents=True, exist_ok=True)
    # M9: use features dict; heartbeat_enabled is @property from features["heartbeat"]
    features = {"heartbeat": True} if heartbeat_enabled else {}
    return AgentWorkspaceConfig(
        agent_id=name,
        workspace_root=workspace_root,
        title=f"Title for {name}",
        features=features,
    )


def test_scheduler_skips_agent_when_heartbeat_disabled(tmp_path: Path) -> None:
    """Agents with heartbeat_enabled=False must be entirely skipped by the scheduler tick.

    feat-394 decision 5: the heartbeat scheduler must gate on the per-agent
    heartbeat_enabled flag from AgentWorkspaceConfig.  When disabled, the scheduler
    must not read HEARTBEAT.md, not submit any run, and report the agent as skipped.
    """
    agent = _agent_with_heartbeat(tmp_path, heartbeat_enabled=False)
    _write_heartbeat(
        agent.workspace_root,
        "interval: 1m\n\n- Check something\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    assert summary.triggered_runs == ()
    assert agent.agent_id in summary.skipped_agents
    assert kernel.sent_messages == []


def test_scheduler_runs_agent_when_heartbeat_enabled(tmp_path: Path) -> None:
    """Agents with heartbeat_enabled=True must be evaluated normally."""
    agent = _agent_with_heartbeat(tmp_path, heartbeat_enabled=True)
    _write_heartbeat(
        agent.workspace_root,
        "interval: 1m\n\n- Check something\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    assert len(summary.triggered_runs) == 1
    assert summary.skipped_agents == ()


def test_scheduler_skips_disabled_among_mixed_agents(tmp_path: Path) -> None:
    """Mixed agent list: disabled agents skipped, enabled agents run normally."""
    enabled = _agent_with_heartbeat(
        tmp_path, name="enabled-agent", heartbeat_enabled=True
    )
    disabled = _agent_with_heartbeat(
        tmp_path, name="disabled-agent", heartbeat_enabled=False
    )
    for agent in (enabled, disabled):
        _write_heartbeat(agent.workspace_root, "interval: 1m\n\n- Check\n")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(enabled, disabled),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    # Only the enabled agent submits a run; the disabled one is skipped.
    triggered_ids = {r.agent_id for r in summary.triggered_runs}
    assert "enabled-agent" in triggered_ids
    assert "disabled-agent" not in triggered_ids
    assert "disabled-agent" in summary.skipped_agents


# ---------------------------------------------------------------------------
# R7: activeHours + busy-skip
# ---------------------------------------------------------------------------


def test_scheduler_skips_agent_outside_active_hours(tmp_path: Path) -> None:
    """Agents with activeHours must be skipped when the current time is outside the window.

    feat-394 decision 3: activeHours from AgentWorkspaceConfig.heartbeat_active_hours_*
    gates the heartbeat tick so out-of-window times don't wake the agent.
    """
    agent = AgentWorkspaceConfig(
        agent_id="agent-ah",
        workspace_root=tmp_path / "agent-ah",
        features={"heartbeat": True},
        heartbeat_active_hours_start="09:00",
        heartbeat_active_hours_end="22:00",
        # No timezone → UTC
    )
    (tmp_path / "agent-ah").mkdir(parents=True, exist_ok=True)
    _write_heartbeat(agent.workspace_root, "interval: 30m\n\n- Check status\n")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    # 03:00 UTC is outside 09:00-22:00 window → skip
    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 3, 0, tzinfo=UTC)))

    assert summary.triggered_runs == ()
    assert agent.agent_id in summary.skipped_agents
    assert kernel.sent_messages == []


def test_scheduler_runs_agent_inside_active_hours(tmp_path: Path) -> None:
    """Agents with activeHours must run normally when the current time is inside the window."""
    agent = AgentWorkspaceConfig(
        agent_id="agent-ah",
        workspace_root=tmp_path / "agent-ah",
        features={"heartbeat": True},
        heartbeat_active_hours_start="09:00",
        heartbeat_active_hours_end="22:00",
    )
    (tmp_path / "agent-ah").mkdir(parents=True, exist_ok=True)
    _write_heartbeat(agent.workspace_root, "interval: 30m\n\n- Check status\n")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    # 10:00 UTC is inside 09:00-22:00 window → run
    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 10, 0, tzinfo=UTC)))

    assert len(summary.triggered_runs) == 1


def test_scheduler_skips_busy_agent_session(tmp_path: Path) -> None:
    """Scheduler must skip an agent when its canonical session is busy (another run in progress).

    feat-394 decision 3: when the canonical direct chat is busy (a user message is being
    processed), the heartbeat must not fire to avoid concurrent runs on the same session.
    """
    # busy_sessions: set of session_ids currently running a kernel job
    busy_sessions: set[str] = {"busy-session-id"}

    agent = _agent_with_heartbeat(tmp_path, heartbeat_enabled=True)
    _write_heartbeat(agent.workspace_root, "interval: 1m\n\n- Check\n")
    kernel = _FakeKernelClient()
    canonical_sessions = {"agent-a": "busy-session-id"}
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        canonical_session_store=canonical_sessions,
        busy_sessions=busy_sessions,
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    # Busy canonical session → skip this tick
    assert summary.triggered_runs == ()
    assert agent.agent_id in summary.skipped_agents
    assert kernel.sent_messages == []
