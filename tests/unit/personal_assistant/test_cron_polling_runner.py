from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig, HeartbeatConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.scheduler.heartbeat_runner import PollingHeartbeatRunner


class _FakeHeartbeatScheduler:
    def __init__(self) -> None:
        self.tick_count = 0
        self.ticked = asyncio.Event()

    async def tick(self) -> Any:
        self.tick_count += 1
        self.ticked.set()

        class _Summary:
            triggered_runs: tuple[object, ...] = ()

        return _Summary()


@pytest.mark.asyncio
async def test_polling_runner_ticks_only_cron_enabled_agents(tmp_path: Path) -> None:
    enabled_workspace = tmp_path / "enabled"
    disabled_workspace = tmp_path / "disabled"
    enabled_workspace.mkdir()
    disabled_workspace.mkdir()
    enabled = AgentWorkspaceConfig(
        agent_id="enabled-agent",
        workspace_root=enabled_workspace,
        features={"cron_scheduling": True},
    )
    disabled = AgentWorkspaceConfig(
        agent_id="disabled-agent",
        workspace_root=disabled_workspace,
        features={},
    )
    cron_called = asyncio.Event()
    cron_ticks: list[str] = []

    async def _cron_tick(agent_id: str) -> None:
        cron_ticks.append(agent_id)
        cron_called.set()

    runner = PollingHeartbeatRunner(
        scheduler=_FakeHeartbeatScheduler(),
        config=HeartbeatConfig(tick_interval_seconds=999),
        cron_tick_fn=_cron_tick,
        agent_catalog=LiveAgentCatalog((enabled, disabled)),
    )

    await runner.start()
    await asyncio.wait_for(cron_called.wait(), timeout=1)
    await runner.close()

    assert cron_ticks == [enabled.agent_id]


@pytest.mark.asyncio
async def test_polling_runner_without_cron_fn_still_ticks_heartbeat() -> None:
    heartbeat = _FakeHeartbeatScheduler()
    runner = PollingHeartbeatRunner(
        scheduler=heartbeat,
        config=HeartbeatConfig(tick_interval_seconds=999),
    )

    await runner.start()
    await asyncio.wait_for(heartbeat.ticked.wait(), timeout=1)
    await runner.close()

    assert heartbeat.tick_count == 1


@pytest.mark.asyncio
async def test_polling_runner_survives_scheduler_tick_failure() -> None:
    class _FlakyHeartbeatScheduler:
        def __init__(self) -> None:
            self.tick_count = 0
            self.first_tick = asyncio.Event()
            self.recovered_tick = asyncio.Event()

        async def tick(self) -> Any:
            self.tick_count += 1
            if self.tick_count == 1:
                self.first_tick.set()
                raise RuntimeError("tick boom")
            self.recovered_tick.set()

            class _Summary:
                triggered_runs: tuple[object, ...] = ()

            return _Summary()

    heartbeat = _FlakyHeartbeatScheduler()
    runner = PollingHeartbeatRunner(
        scheduler=heartbeat,
        config=HeartbeatConfig(tick_interval_seconds=999),
    )

    await runner.start()
    await asyncio.wait_for(heartbeat.first_tick.wait(), timeout=1)
    runner.request_tick()
    await asyncio.wait_for(heartbeat.recovered_tick.wait(), timeout=1)
    await runner.close()

    assert heartbeat.tick_count == 2
