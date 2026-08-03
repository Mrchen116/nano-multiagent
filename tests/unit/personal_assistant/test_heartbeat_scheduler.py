from __future__ import annotations

import asyncio
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
            "metadata": metadata,
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


def _agent(tmp_path: Path, name: str = "agent-a") -> AgentWorkspaceConfig:
    workspace_root = tmp_path / name
    workspace_root.mkdir(parents=True, exist_ok=True)
    return AgentWorkspaceConfig(
        agent_id=name,
        workspace_root=workspace_root,
        title=f"Title for {name}",
        features={"heartbeat": True},
    )


def _write_heartbeat(workspace_root: Path, content: str) -> None:
    (workspace_root / "HEARTBEAT.md").write_text(content, encoding="utf-8")


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


def test_scheduler_passes_agent_model_to_submit(tmp_path: Path) -> None:
    workspace_root = tmp_path / "gpt-agent"
    workspace_root.mkdir(parents=True, exist_ok=True)
    agent = AgentWorkspaceConfig(
        agent_id="gpt-agent",
        workspace_root=workspace_root,
        title="GPT Agent",
        features={"heartbeat": True},
        default_model="codex_oauth:gpt-5.5",
    )
    _write_heartbeat(agent.workspace_root, "- Check inbox status\n")
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    assert kernel.sent_messages[0]["model"] == "codex_oauth:gpt-5.5"


@pytest.mark.asyncio
async def test_heartbeat_session_metadata_contains_agent_id(tmp_path: Path) -> None:
    """Heartbeat-created sessions retain the agent route used by cron tools."""
    agent = _agent(tmp_path, name="hb-agent")
    _write_heartbeat(
        agent.workspace_root,
        "tasks:\n- name: check\n  instruction: Run cron job.\n",
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    await scheduler.tick(now=datetime(2026, 6, 11, 9, 0, tzinfo=UTC))

    assert kernel.created_sessions[0]["metadata"] == {"agent_id": agent.agent_id}
