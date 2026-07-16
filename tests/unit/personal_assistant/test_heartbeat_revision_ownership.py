"""Heartbeat session caches follow the captured live Agent revision."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


class _Kernel:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.submitted: list[dict[str, object]] = []

    async def create_session(self, **kwargs: object) -> dict[str, object]:
        self.created.append(kwargs)
        return {"session_id": f"heartbeat-{len(self.created)}"}

    def submit_message(self, **kwargs: object) -> dict[str, object]:
        self.submitted.append(kwargs)
        return {"run_id": f"run-{len(self.submitted)}"}

    def current_event_sequence(self) -> int:
        return 0


def _agent(workspace: Path, *, prompt: str) -> AgentWorkspaceConfig:
    workspace.mkdir()
    (workspace / "HEARTBEAT.md").write_text("- check\n", encoding="utf-8")
    return AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        features={"heartbeat": True},
        heartbeat_every="1s",
        custom_prompt=prompt,
    )


def test_config_publish_invalidates_heartbeat_session_cache(tmp_path: Path) -> None:
    """The next heartbeat tick cannot reuse a session created for an old revision."""

    old = _agent(tmp_path / "old", prompt="old")
    catalog = LiveAgentCatalog((old,))
    kernel = _Kernel()
    scheduler = HeartbeatScheduler(
        agents=(old,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        agent_catalog=catalog,
    )
    start = datetime(2026, 7, 15, tzinfo=UTC)
    asyncio.run(scheduler.tick(now=start))

    new = _agent(tmp_path / "new", prompt="new")
    catalog.publish(new)
    asyncio.run(scheduler.tick(now=start + timedelta(seconds=2)))

    assert [call["workspace_root"] for call in kernel.created] == [
        str(old.workspace_root),
        str(new.workspace_root),
    ]
    assert [call["session_id"] for call in kernel.submitted] == [
        "heartbeat-1",
        "heartbeat-2",
    ]
