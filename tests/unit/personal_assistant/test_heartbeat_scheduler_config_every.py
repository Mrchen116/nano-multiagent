from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
    _AgentState,
    _SchedulerState,
)


class _FakeKernelClient:
    """Sync fake client — used by config_every / live_agents_getter tests."""

    def __init__(self) -> None:
        self.created_sessions: list[dict[str, object]] = []
        self.sent_messages: list[dict[str, object]] = []
        self._session_counter = 0
        self._run_counter = 0

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self._session_counter += 1
        payload: dict[str, object] = {
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
    """Create an agent fixture with explicit heartbeat enable state via features dict."""
    workspace_root = tmp_path / name
    workspace_root.mkdir(parents=True, exist_ok=True)
    features = {"heartbeat": True} if heartbeat_enabled else {}
    return AgentWorkspaceConfig(
        agent_id=name,
        workspace_root=workspace_root,
        title=f"Title for {name}",
        features=features,
    )


def test_scheduler_uses_live_agents_getter_on_each_tick(tmp_path: Path) -> None:
    """HeartbeatScheduler must read live agent config from agents_getter on each tick.

    S1.3 fix: HeartbeatScheduler._agents was an immutable tuple frozen at init
    time.  ConfigSyncNotifier updates pipeline._agents dynamically, but the
    scheduler never saw the changes — toggle off required gateway restart.

    After the fix, when agents_getter is provided it is called on each tick so
    the scheduler immediately picks up changes (e.g. heartbeat_enabled=False).
    """
    agent = _agent_with_heartbeat(tmp_path, heartbeat_enabled=True)
    _write_heartbeat(agent.workspace_root, "interval: 1m\n\n- Check\n")
    kernel = _FakeKernelClient()

    # Start with heartbeat_enabled=True
    live_agents: dict[str, AgentWorkspaceConfig] = {agent.agent_id: agent}

    scheduler = HeartbeatScheduler(
        agents=(),  # empty frozen tuple — all reads come from getter
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        agents_getter=lambda: list(live_agents.values()),
    )

    # First tick: agent is enabled → should fire
    summary1 = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))
    assert len(summary1.triggered_runs) == 1, "agent should fire when enabled"

    # Simulate config toggle: heartbeat_enabled=False (M9: use features={} not heartbeat_enabled field)
    disabled_agent = AgentWorkspaceConfig(
        agent_id=agent.agent_id,
        workspace_root=agent.workspace_root,
        features={},
    )
    live_agents[agent.agent_id] = disabled_agent

    # Second tick (1 minute later): agent is now disabled → must NOT fire
    summary2 = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 1, tzinfo=UTC)))
    assert summary2.triggered_runs == (), "agent must be skipped after toggle off"
    assert disabled_agent.agent_id in summary2.skipped_agents


def test_scheduler_falls_back_to_frozen_agents_when_no_getter(tmp_path: Path) -> None:
    """When agents_getter is None, scheduler uses the frozen _agents tuple (backward compat)."""
    agent = _agent_with_heartbeat(tmp_path, heartbeat_enabled=True)
    _write_heartbeat(agent.workspace_root, "interval: 1m\n\n- Check\n")
    kernel = _FakeKernelClient()

    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        # no agents_getter — uses frozen tuple
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))
    assert len(summary.triggered_runs) == 1


# feat-394-M11 decision E: cadence is the single source of truth — scheduler reads
# agent.heartbeat_every from config, not HEARTBEAT.md top-level every: line.


def test_scheduler_uses_config_every_when_heartbeat_every_is_set(
    tmp_path: Path,
) -> None:
    """Toplevel node rhythm comes from agent.heartbeat_every (config), not HEARTBEAT.md every:.

    When HEARTBEAT.md has a top-level "every: 5m" line but agent.heartbeat_every is "60m",
    the scheduler must use the config value (60m) and ignore the md line.
    This is the openclaw-aligned behaviour: md top-level every is retired, config is SoT.
    """
    agent = AgentWorkspaceConfig(
        agent_id="agent-cfg-sot",
        workspace_root=tmp_path / "agent-cfg-sot",
        heartbeat_every="60m",
        features={"heartbeat": True},
    )
    (tmp_path / "agent-cfg-sot").mkdir()
    # md file declares "every: 5m" — must be ignored in favour of config "60m"
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\nevery: 5m\n\n- Check inbox\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    # First tick at T=0 — should fire (no prior state)
    first = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 0, tzinfo=UTC)))
    # 30 minutes later — within 60m window, must NOT fire again
    mid = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 30, tzinfo=UTC)))
    # 60 minutes after first — must fire again
    second = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 10, 0, tzinfo=UTC)))

    assert len(first.triggered_runs) == 1, "first tick should fire"
    assert mid.triggered_runs == (), "30m < 60m config cadence — must not fire"
    assert len(second.triggered_runs) == 1, "60m elapsed — should fire again"
    assert len(kernel.sent_messages) == 2


def test_scheduler_uses_default_30m_when_heartbeat_every_is_none(
    tmp_path: Path,
) -> None:
    """When agent.heartbeat_every is None, default to 30m (openclaw DEFAULT_HEARTBEAT_EVERY).

    The HEARTBEAT.md has only freeform instructions (no top-level every: line); the
    scheduler must infer 30m from the absent config field and run accordingly.
    """
    agent = AgentWorkspaceConfig(
        agent_id="agent-default30",
        workspace_root=tmp_path / "agent-default30",
        heartbeat_every=None,  # not configured — scheduler should default to 30m
        features={"heartbeat": True},
    )
    (tmp_path / "agent-default30").mkdir()
    # md has tasks content but NO top-level every: line — freeform instructions only
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\n- Check for new messages\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    # T=0 — fires
    first = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 0, tzinfo=UTC)))
    # T=20m — within 30m default, must not fire
    early = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 20, tzinfo=UTC)))
    # T=30m — must fire (default 30m elapsed)
    second = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 30, tzinfo=UTC)))

    assert len(first.triggered_runs) == 1
    assert early.triggered_runs == (), "20m < 30m default — must not fire"
    assert len(second.triggered_runs) == 1
    assert len(kernel.sent_messages) == 2


def test_scheduler_ignores_md_top_level_every_when_config_every_set(
    tmp_path: Path,
) -> None:
    """md top-level every: is completely ignored when agent.heartbeat_every is set.

    If md "every: 1m" were honoured, the scheduler would fire every minute.
    With config "2h", a tick 90 seconds after the first must NOT fire a second run.
    This proves the md every: line is silenced and config cadence governs.
    """
    agent = AgentWorkspaceConfig(
        agent_id="agent-ignore-md",
        workspace_root=tmp_path / "agent-ignore-md",
        heartbeat_every="2h",
        features={"heartbeat": True},
    )
    (tmp_path / "agent-ignore-md").mkdir()
    # md declares very short every: 1m — must be fully ignored
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\nevery: 1m\n\n- Check something\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    first = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 0, tzinfo=UTC)))
    # 90 seconds later — if md "every: 1m" were used, a second run would fire.
    # With config "2h", this must remain silent.
    ninety_sec = asyncio.run(
        scheduler.tick(now=datetime(2026, 6, 8, 9, 1, 30, tzinfo=UTC))
    )

    assert len(first.triggered_runs) == 1
    assert ninety_sec.triggered_runs == (), (
        "90s after first tick — md every:1m must be ignored; config 2h must not fire yet"
    )


def test_scheduler_tasks_per_task_rhythm_unaffected_by_config_every(
    tmp_path: Path,
) -> None:
    """tasks: per-task sub-rhythms are read from md and unaffected by agent.heartbeat_every.

    When HEARTBEAT.md has a tasks: block, each task's own interval: is used.
    agent.heartbeat_every applies to the top-level fallback only (no tasks: block).
    """
    agent = AgentWorkspaceConfig(
        agent_id="agent-tasks-rhythm",
        workspace_root=tmp_path / "agent-tasks-rhythm",
        heartbeat_every="2h",  # top-level cadence — irrelevant when tasks: block present
        features={"heartbeat": True},
    )
    (tmp_path / "agent-tasks-rhythm").mkdir()
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ntasks:\n  - name: inbox\n    interval: 15m\n    prompt: Check inbox\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    first = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 0, tzinfo=UTC)))
    # 15m later — task interval due, must fire
    second = asyncio.run(scheduler.tick(now=datetime(2026, 6, 8, 9, 15, tzinfo=UTC)))

    assert len(first.triggered_runs) == 1, "tasks: task fires on first tick"
    assert len(second.triggered_runs) == 1, (
        "15m task interval elapsed — should fire again"
    )
    assert len(kernel.sent_messages) == 2
