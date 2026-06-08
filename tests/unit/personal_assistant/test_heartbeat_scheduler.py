from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


class _FakeKernelClient:
    """Sync fake client — used by existing tests that don't exercise the async path."""

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
        """Return 0 as a stub anchor (tests do not exercise stream-from-anchor path)."""
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


def _agent(tmp_path: Path, name: str = "agent-a") -> AgentWorkspaceConfig:
    workspace_root = tmp_path / name
    workspace_root.mkdir(parents=True, exist_ok=True)
    # features={"heartbeat": True}: tests that exercise scheduling logic need the gate open.
    # M9: heartbeat_enabled is @property from features["heartbeat"].
    return AgentWorkspaceConfig(
        agent_id=name,
        workspace_root=workspace_root,
        title=f"Title for {name}",
        features={"heartbeat": True},
    )


def _write_heartbeat(workspace_root: Path, content: str) -> Path:
    path = workspace_root / "HEARTBEAT.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_scheduler_skips_quietly_when_heartbeat_has_no_actionable_task(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(agent.workspace_root, "# Heartbeat\n\n<!-- comment only -->\n")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

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
    scheduler = HeartbeatScheduler(
        agents=(agent,), kernel_client=kernel, state_store=state_store
    )

    first = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))
    second = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 10, tzinfo=UTC)))
    third = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 30, tzinfo=UTC)))

    assert len(first.triggered_runs) == 1
    assert second.triggered_runs == ()
    assert len(third.triggered_runs) == 1
    assert len(kernel.sent_messages) == 2
    assert (
        state_store.load().agents[agent.agent_id].last_due_at
        == "2026-03-11T09:30:00+00:00"
    )


def test_scheduler_runs_at_schedule_only_once_even_across_restart(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\nat: 2026-03-11T09:00:00+00:00\n\n- Submit daily digest\n",
    )
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    kernel = _FakeKernelClient()

    scheduler = HeartbeatScheduler(
        agents=(agent,), kernel_client=kernel, state_store=state_store
    )
    first = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    restarted = HeartbeatScheduler(
        agents=(agent,), kernel_client=kernel, state_store=state_store
    )
    second = asyncio.run(restarted.tick(now=datetime(2026, 3, 11, 10, 0, tzinfo=UTC)))

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

    before = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 8, 59, tzinfo=UTC)))
    due = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    assert before.triggered_runs == ()
    assert len(due.triggered_runs) == 1
    assert len(kernel.sent_messages) == 1


def test_interval_no_backfill_after_restart(tmp_path: Path) -> None:
    """After a long gap, restart fires exactly once (most-recent slot) — no backfill flood.

    feat-394-M8 R6-1 fix: floor(elapsed/interval) semantics.
    Before fix (ceil): restart after large gap jumped to next *future* slot → no run at all.
    After fix (floor): restart fires the most-recent past slot exactly once (not all N missed),
    then advances last_due_at to that slot so the next tick waits a full interval.

    The key invariant is "no flood" (exactly 1 run per tick) — not "never run anything past".
    """
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ninterval: 30m\n\n- Follow up on outstanding tasks\n",
    )
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    first_kernel = _FakeKernelClient()
    first_scheduler = HeartbeatScheduler(
        agents=(agent,), kernel_client=first_kernel, state_store=state_store
    )

    first = asyncio.run(
        first_scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))
    )
    assert len(first.triggered_runs) == 1

    second_kernel = _FakeKernelClient()
    restarted = HeartbeatScheduler(
        agents=(agent,), kernel_client=second_kernel, state_store=state_store
    )
    # 1h31m gap — 3 missed intervals (09:30, 10:00, 10:30).
    # floor semantics: steps=floor(91/30)=3, next_due=09:00+90m=10:30 ≤ 10:31 → fires once.
    # Not 3 times (no flood). last_due_at advances to 10:30.
    catch_up = asyncio.run(
        restarted.tick(now=datetime(2026, 3, 11, 10, 31, tzinfo=UTC))
    )
    assert len(catch_up.triggered_runs) == 1, (
        "restart after large gap must fire exactly once (most-recent slot), not N times"
    )

    # Next tick at 10:31 again — already fired this slot, must not fire again.
    # (elapsed from 10:30 to 10:31 = 1m < 30m → no trigger)
    no_double = asyncio.run(
        restarted.tick(now=datetime(2026, 3, 11, 10, 31, tzinfo=UTC))
    )
    assert no_double.triggered_runs == (), "must not double-fire the same slot"

    # Next tick at 11:00 (full interval after 10:30 last_due) must fire.
    next_tick = asyncio.run(
        restarted.tick(now=datetime(2026, 3, 11, 11, 0, tzinfo=UTC))
    )
    assert len(next_tick.triggered_runs) == 1


def test_scheduler_normal_cadence_produces_exactly_one_run_per_interval(
    tmp_path: Path,
) -> None:
    """Continuous operation: each on-time tick produces exactly 1 triggered run.

    feat-394-M11 decision E: cadence comes from agent.heartbeat_every (config), not md.
    md contains only freeform instructions; interval: line is retired.
    """
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=tmp_path / "agent-a",
        heartbeat_every="10s",  # config is SoT for cadence (decision E)
        features={"heartbeat": True},
    )
    (tmp_path / "agent-a").mkdir()
    _write_heartbeat(agent.workspace_root, "Report status.\n")  # no interval: line
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    scheduler = HeartbeatScheduler(
        agents=(agent,), kernel_client=_FakeKernelClient(), state_store=state_store
    )

    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    for offset_s in (0, 10, 20, 30):
        result = asyncio.run(scheduler.tick(now=t0 + timedelta(seconds=offset_s)))
        assert len(result.triggered_runs) == 1, (
            f"at +{offset_s}s expected 1 run, got {len(result.triggered_runs)}"
        )


def test_cron_no_backfill_after_restart(tmp_path: Path) -> None:
    """Cron restart must run exactly the CURRENT minute if it matches, not past missed minutes.

    feat-394 decision 3/4 (openclaw semantics): cron checks whether the current tick's
    minute matches the expression AND has not already been executed.  It does NOT replay
    past missed slots.  So "* * * * *" after a 5-minute gap fires exactly once for the
    current minute — not 5 separate runs for the gap.

    Contrast: the old feat-393 fix-r2 approach scanned from last_due_at to now and would
    yield the most-recent match (still a form of backfill).  openclaw fires only the
    present minute, leaving the gap silently un-executed.
    """
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root, "cron: 0 9 * * *\n\nDaily 09:00 heartbeat.\n"
    )
    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,), kernel_client=kernel, state_store=state_store
    )

    # First tick at 09:00 on day 1 — fires, establishes last_due_at.
    first = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))
    assert len(first.triggered_runs) == 1

    # Restart after 25h gap — missed the 09:00 on day 2.
    # openclaw semantics: 10:00 on day 2 does NOT match "0 9 * * *", so no run.
    restarted = HeartbeatScheduler(
        agents=(agent,), kernel_client=_FakeKernelClient(), state_store=state_store
    )
    catch_up = asyncio.run(restarted.tick(now=datetime(2026, 3, 12, 10, 0, tzinfo=UTC)))

    assert catch_up.triggered_runs == (), (
        "cron restart must NOT backfill past missed slots — only fire on the current matching minute"
    )

    # Next cron slot (09:00 on day 3) must fire when the tick lands on that minute.
    next_tick = asyncio.run(restarted.tick(now=datetime(2026, 3, 13, 9, 0, tzinfo=UTC)))
    assert len(next_tick.triggered_runs) == 1
    assert next_tick.triggered_runs[0].due_at == datetime(2026, 3, 13, 9, 0, tzinfo=UTC)


def test_scheduler_rejects_multiple_explicit_schedule_modes_in_one_heartbeat(
    tmp_path: Path,
) -> None:
    """HEARTBEAT.md must not declare more than one at:/cron: entry.

    feat-394-M11 decision E: every:/interval: lines are retired (silently ignored).
    at: and cron: lines are still parsed and must not conflict.
    A file with two at: entries (or two cron: entries) raises ValueError.
    """
    agent = _agent(tmp_path)
    # Two cron: entries — must raise (only at:/cron: entries are counted now)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ncron: 0 9 * * *\ncron: 0 18 * * *\n\n- invalid\n",
    )
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=_FakeKernelClient(),
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    with pytest.raises(ValueError, match="at most one explicit schedule mode"):
        asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))


@pytest.mark.asyncio
async def test_scheduler_tick_from_async_context_completes_without_event_loop_error(
    tmp_path: Path,
) -> None:
    """tick() must be awaitable from an async context without RuntimeError.

    Regression: _KernelClientShim used run_until_complete inside an already-running
    loop, causing 'This event loop is already running' — heartbeat runs were silently
    never submitted.  After the fix, tick() is a coroutine and create_session is async
    so the call chain is properly awaited end-to-end.
    """
    agent = _agent(tmp_path)
    _write_heartbeat(
        agent.workspace_root,
        "# Heartbeat\n\ninterval: 1m\n\n- Check status\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    # This must not raise RuntimeError("This event loop is already running")
    summary = await scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC))

    # The run was actually submitted — not silently dropped
    assert len(summary.triggered_runs) == 1
    assert len(kernel.created_sessions) == 1
    assert kernel.created_sessions[0]["session_id"] == "sess-1"
    assert len(kernel.sent_messages) == 1
    assert kernel.sent_messages[0]["run_id"] == "run-1"


# ---------------------------------------------------------------------------
# R2: per-agent heartbeat_enabled gate
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# R6: tasks: multi-sub-rhythm + canonical session
# ---------------------------------------------------------------------------


def test_heartbeat_spec_parses_tasks_block_multi_rhythm(tmp_path: Path) -> None:
    """_load_heartbeat_spec must parse HEARTBEAT.md tasks: block into per-task schedules.

    Provenance: openclaw/src/auto-reply/heartbeat.ts:parseHeartbeatTasks
    feat-394 decision 3: tasks: block defines multiple sub-rhythms, each independently
    tracked with its own last_due_at.
    """
    from personal_assistant.scheduler.heartbeat_scheduler import _load_heartbeat_spec

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    hb_path = agent_dir / "HEARTBEAT.md"
    hb_path.write_text(
        "# Heartbeat\n\n"
        "tasks:\n"
        "  - name: inbox-check\n"
        "    interval: 30m\n"
        '    prompt: "Check for urgent emails"\n'
        "  - name: schedule-review\n"
        "    interval: 2h\n"
        '    prompt: "Review upcoming schedule"\n',
        encoding="utf-8",
    )

    spec = _load_heartbeat_spec(hb_path)

    assert spec is not None, "spec must not be None for non-empty tasks: block"
    # Multi-task spec should have multiple tasks
    assert hasattr(spec, "tasks"), "spec must have a tasks attribute for tasks: block"
    assert len(spec.tasks) == 2
    task_names = [t.name for t in spec.tasks]
    assert "inbox-check" in task_names
    assert "schedule-review" in task_names


def test_heartbeat_scheduler_uses_provided_canonical_session(tmp_path: Path) -> None:
    """HeartbeatScheduler must use the canonical session_id when provided, not create a new one.

    feat-394 decision 3: heartbeat runs in the (owner, agent) canonical direct chat
    kernel session.  When a canonical session_id is pre-known, the scheduler must
    not call create_session.
    """
    agent = _agent_with_heartbeat(tmp_path, heartbeat_enabled=True)
    _write_heartbeat(agent.workspace_root, "interval: 1m\n\n- Check status\n")
    kernel = _FakeKernelClient()

    # Pre-supply a canonical session_id as if it was established by a prior direct chat.
    canonical_sessions: dict[str, str] = {"agent-a": "canonical-sess-123"}

    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        canonical_session_store=canonical_sessions,
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    # Session creation must be skipped — canonical session used directly
    assert kernel.created_sessions == [], (
        "create_session must not be called when canonical_session_store has a session for this agent"
    )
    assert len(summary.triggered_runs) == 1
    # The run must use the canonical session_id
    assert summary.triggered_runs[0].session_id == "canonical-sess-123"


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


# ---------------------------------------------------------------------------
# feat-394-M4 R3: per-tick live agent config (S1.3 hot-reload)
# ---------------------------------------------------------------------------


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


def test_heartbeat_interval_triggers_on_second_tick_with_overhead(
    tmp_path: Path,
) -> None:
    """Regression for R6-1 ceil bug in heartbeat _IntervalSchedule.

    Scenario: interval=30s, LLM call + overhead makes elapsed=32s on second tick.
    ceil(32/30)=2 → next_due=last+60s > now+32s → NOT triggered (the bug).
    floor(32/30)=1 → next_due=last+30s <= now+32s → triggered (correct).
    """
    from personal_assistant.scheduler.heartbeat_scheduler import (
        _AgentState,
        _SchedulerState,
    )

    # feat-394-M11 decision E: cadence from config, not md.
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=tmp_path / "agent-a",
        heartbeat_every="30s",  # config is SoT (decision E)
        features={"heartbeat": True},
    )
    (tmp_path / "agent-a").mkdir()
    _write_heartbeat(agent.workspace_root, "- Check task\n")  # no interval: line
    kernel = _FakeKernelClient()

    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    # Set last_due_at to T; simulate second tick at T+32s (30s sleep + 2s LLM overhead)
    t_last = datetime(2026, 3, 11, 9, 0, 0, tzinfo=UTC)
    t_second_tick = t_last + timedelta(seconds=32)
    state_store.save(
        _SchedulerState(
            agents={
                agent.agent_id: _AgentState(last_due_at=t_last.isoformat()),
            }
        )
    )

    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=state_store,
    )
    summary = asyncio.run(scheduler.tick(now=t_second_tick))
    assert len(summary.triggered_runs) == 1, (
        "Second heartbeat tick (elapsed=32s, interval=30s) must trigger; "
        "ceil bug gives steps=2, next_due=last+60s > now → not fired"
    )


def test_heartbeat_large_gap_triggers_only_once(tmp_path: Path) -> None:
    """Regression: large gap (5 missed heartbeat intervals) must fire exactly once.

    Verifies the floor fix does not re-introduce round-2 backfill flood.
    """
    from personal_assistant.scheduler.heartbeat_scheduler import (
        _AgentState,
        _SchedulerState,
    )

    # feat-394-M11 decision E: cadence from config, not md.
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=tmp_path / "agent-a",
        heartbeat_every="30s",  # config is SoT (decision E)
        features={"heartbeat": True},
    )
    (tmp_path / "agent-a").mkdir()
    _write_heartbeat(agent.workspace_root, "- Check task\n")  # no interval: line
    kernel = _FakeKernelClient()

    state_store = HeartbeatSchedulerStateStore(tmp_path / "state.json")
    t_last = datetime(2026, 3, 11, 9, 0, 0, tzinfo=UTC)
    t_now = t_last + timedelta(seconds=150)  # 5 missed intervals of 30s
    state_store.save(
        _SchedulerState(
            agents={
                agent.agent_id: _AgentState(last_due_at=t_last.isoformat()),
            }
        )
    )

    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=state_store,
    )
    summary = asyncio.run(scheduler.tick(now=t_now))
    assert len(summary.triggered_runs) == 1, (
        f"Large gap must trigger exactly 1 heartbeat, got {len(summary.triggered_runs)}"
    )


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
