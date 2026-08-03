"""Heartbeat canonical-session and live-runtime behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from personal_assistant.channels.base import ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_keys import SessionBinding
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


def _write_heartbeat(workspace_root: Path) -> None:
    (workspace_root / "HEARTBEAT.md").write_text(
        "- Check status\n", encoding="utf-8"
    )


def test_heartbeat_scheduler_uses_current_canonical_binding_before_submit(
    tmp_path: Path,
) -> None:
    agent_dir = tmp_path / "agent-tick"
    agent_dir.mkdir()
    _write_heartbeat(agent_dir)
    agent = AgentWorkspaceConfig(
        agent_id="agent-tick",
        workspace_root=agent_dir,
        features={"heartbeat": True},
    )
    expected_session = "sess-from-direct-chat"

    class _FakeSessionBinder:
        def find_canonical_direct(
            self, *, channel_name: str, agent_id: str
        ) -> SessionBinding | None:
            assert channel_name == "web_relay"
            if agent_id != agent.agent_id:
                return None
            return SessionBinding(
                session_key=f"web_relay:conv-direct:{agent_id}",
                kernel_session_id=expected_session,
                reply_context=ReplyContext(
                    channel_name="web_relay",
                    target_chat_id="conv-direct",
                    thread_id=None,
                    metadata={},
                ),
            )

    class _FakeKernelClient:
        def __init__(self) -> None:
            self.created_sessions = 0
            self.sent_messages: list[dict[str, object]] = []

        async def create_session(self, **_kwargs: object) -> dict[str, str]:
            self.created_sessions += 1
            return {"session_id": "sess-fallback"}

        def current_event_sequence(self) -> int:
            return 0

        def submit_message(
            self, *, session_id: str, **_kwargs: object
        ) -> dict[str, str]:
            self.sent_messages.append({"session_id": session_id})
            return {"run_id": "run-1", "session_id": session_id}

    canonical_sessions: dict[str, str] = {}
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        canonical_session_store=canonical_sessions,
        session_binder=_FakeSessionBinder(),
    )

    asyncio.run(scheduler.tick(now=datetime(2026, 6, 1, 9, 0, tzinfo=UTC)))

    assert canonical_sessions == {agent.agent_id: expected_session}
    assert kernel.created_sessions == 0
    assert kernel.sent_messages == [{"session_id": expected_session}]


def test_heartbeat_scheduler_reuses_stable_session_across_due_ticks(
    tmp_path: Path,
) -> None:
    class _FakeKernelClient:
        def __init__(self) -> None:
            self.created_sessions: list[str] = []
            self.sent_messages: list[str] = []

        async def create_session(self, **_kwargs: object) -> dict[str, str]:
            session_id = f"sess-{len(self.created_sessions) + 1}"
            self.created_sessions.append(session_id)
            return {"session_id": session_id}

        def submit_message(
            self, *, session_id: str, **_kwargs: object
        ) -> dict[str, str]:
            self.sent_messages.append(session_id)
            return {"run_id": f"run-{len(self.sent_messages)}"}

    agent_dir = tmp_path / "agent-a"
    agent_dir.mkdir()
    _write_heartbeat(agent_dir)
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=agent_dir,
        heartbeat_every="1s",
        features={"heartbeat": True},
    )
    kernel = _FakeKernelClient()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )
    first_due = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

    asyncio.run(scheduler.tick(now=first_due))
    asyncio.run(scheduler.tick(now=first_due + timedelta(seconds=2)))

    assert kernel.created_sessions == ["sess-1"]
    assert kernel.sent_messages == ["sess-1", "sess-1"]


def test_heartbeat_reused_session_aligns_current_agent_runtime(tmp_path: Path) -> None:
    workspace = tmp_path / "agent-runtime"
    workspace.mkdir()
    _write_heartbeat(workspace)
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-runtime",
                workspace_root=workspace,
                features={"heartbeat": True},
            ),
        )
    )

    class _RuntimeAwareKernel:
        def __init__(self) -> None:
            self.runtime_calls: list[dict[str, object]] = []

        async def create_session(self, **_kwargs: object) -> dict[str, str]:
            return {"session_id": "heartbeat-session"}

        async def ensure_agent_runtime(self, **kwargs: object) -> None:
            self.runtime_calls.append(dict(kwargs))

        def submit_message(self, **_kwargs: object) -> dict[str, str]:
            return {"run_id": "heartbeat-run"}

    kernel = _RuntimeAwareKernel()
    scheduler = HeartbeatScheduler(
        agents=(),
        agent_catalog=catalog,
        kernel_client=kernel,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )

    asyncio.run(scheduler.tick(now=datetime(2026, 6, 1, 9, 0, tzinfo=UTC)))

    assert kernel.runtime_calls == [
        {
            "session_id": "heartbeat-session",
            "agent_snapshot": catalog.require("agent-runtime"),
            "workspace_root": str(workspace),
            "metadata": {"agent_id": "agent-runtime"},
        }
    ]
