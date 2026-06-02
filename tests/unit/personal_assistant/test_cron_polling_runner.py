"""Tests for feat-394-M3 R2: cron接入 PollingHeartbeatRunner gateway 运行循环.

CRITICAL-1 fix: CronScheduler/CronRunner were only referenced by tests; main.py
never imported or invoked them. The gateway polling loop only ran heartbeat ticks.

These tests verify that:
1. The polling runner evaluates cron jobs on each tick for cron_enabled agents.
2. Due cron jobs are submitted (CronScheduler.tick is called).
3. agents with cron_enabled=False are skipped.

feat-394 architecture: 统一 polling tick 驱动 heartbeat + cron 两套（design 架构图）。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig, HeartbeatConfig
from personal_assistant.scheduler.cron_scheduler import (
    CronJob,
    CronJobStore,
    CronScheduler,
    CronSchedulerStateStore,
)
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


# ---------------------------------------------------------------------------
# Fakes / helpers
# ---------------------------------------------------------------------------


class _FakeHeartbeatScheduler:
    """Heartbeat scheduler stub that returns empty summary."""

    def __init__(self) -> None:
        self.tick_count = 0

    async def tick(self) -> Any:
        self.tick_count += 1

        class _Summary:
            triggered_runs: list = []

        return _Summary()


class _FakeCronScheduler:
    """CronScheduler stub that records tick calls."""

    def __init__(self) -> None:
        self.tick_count = 0
        self.tick_args: list[dict] = []

    async def tick(self, *, now=None) -> None:
        self.tick_count += 1
        self.tick_args.append({"now": now})


class _PipelineLike:
    """Minimal pipeline-like object with agents dict."""

    def __init__(self, agents: dict[str, AgentWorkspaceConfig]) -> None:
        self._agents = agents


# ---------------------------------------------------------------------------
# Tests: cron tick接入 polling runner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_polling_runner_calls_cron_tick_for_cron_enabled_agent(
    tmp_path: Path,
) -> None:
    """PollingHeartbeatRunner._run_loop must call cron tick for agents with cron_enabled=True.

    CRITICAL-1: Before the fix, CronScheduler was never called by the gateway loop.
    After the fix, each polling tick must evaluate cron jobs for each cron_enabled agent.
    """
    from personal_assistant.main import PollingHeartbeatRunner

    ws = tmp_path / "ws-agent"
    ws.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="cron-agent",
        workspace_root=ws,
        cron_enabled=True,
    )

    cron_ticks: list[str] = []

    async def _fake_cron_tick_fn(agent_id: str) -> None:
        cron_ticks.append(agent_id)

    hb_scheduler = _FakeHeartbeatScheduler()
    hb_config = HeartbeatConfig(tick_interval_seconds=999)

    # Build runner with the cron tick fn injected.
    runner = PollingHeartbeatRunner(
        scheduler=hb_scheduler,
        config=hb_config,
        cron_tick_fn=_fake_cron_tick_fn,
        agents={"cron-agent": agent},
    )

    await runner.start()
    # Give the loop one chance to run.
    await asyncio.sleep(0.01)
    await runner.close()

    assert len(cron_ticks) >= 1, (
        "cron_tick_fn must be called at least once per polling loop tick "
        "(CRITICAL-1: cron was never wired into the gateway run loop)"
    )
    assert "cron-agent" in cron_ticks


@pytest.mark.asyncio
async def test_polling_runner_skips_cron_tick_for_cron_disabled_agent(
    tmp_path: Path,
) -> None:
    """PollingHeartbeatRunner must NOT call cron tick for agents with cron_enabled=False."""
    from personal_assistant.main import PollingHeartbeatRunner

    ws = tmp_path / "ws-nocron"
    ws.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="nocron-agent",
        workspace_root=ws,
        cron_enabled=False,
    )

    cron_ticks: list[str] = []

    async def _fake_cron_tick_fn(agent_id: str) -> None:
        cron_ticks.append(agent_id)

    hb_scheduler = _FakeHeartbeatScheduler()
    hb_config = HeartbeatConfig(tick_interval_seconds=999)

    runner = PollingHeartbeatRunner(
        scheduler=hb_scheduler,
        config=hb_config,
        cron_tick_fn=_fake_cron_tick_fn,
        agents={"nocron-agent": agent},
    )

    await runner.start()
    await asyncio.sleep(0.01)
    await runner.close()

    # nocron-agent has cron_enabled=False → must NOT be in cron_ticks
    assert "nocron-agent" not in cron_ticks, (
        "cron_tick_fn must NOT be called for agents with cron_enabled=False"
    )


@pytest.mark.asyncio
async def test_polling_runner_without_cron_fn_runs_normally(
    tmp_path: Path,
) -> None:
    """PollingHeartbeatRunner without cron_tick_fn must still work (backward compat)."""
    from personal_assistant.main import PollingHeartbeatRunner

    hb_scheduler = _FakeHeartbeatScheduler()
    hb_config = HeartbeatConfig(tick_interval_seconds=999)

    runner = PollingHeartbeatRunner(
        scheduler=hb_scheduler,
        config=hb_config,
        # no cron_tick_fn passed
    )

    await runner.start()
    await asyncio.sleep(0.01)
    await runner.close()

    assert hb_scheduler.tick_count >= 1
