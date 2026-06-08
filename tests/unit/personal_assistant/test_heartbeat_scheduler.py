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
