"""Concurrency behavior tests for Gateway session binding ownership."""

from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event as ThreadEvent
from types import SimpleNamespace
from typing import Any

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import (
    ConversationBindingRequest,
    GatewaySessionBinder,
    SessionBindingRequest,
)


class _SlowValidationKernel:
    def __init__(self, *, slow_session_id: str) -> None:
        self.slow_session_id = slow_session_id
        self.validation_started = ThreadEvent()
        self.validation_finished = ThreadEvent()
        self.release_validation = ThreadEvent()
        self.sessions: dict[str, str] = {}
        self.create_calls: list[str] = []
        self.validation_calls: list[str] = []

    def get_session(self, *, session_id: str, workspace_root: str) -> dict[str, str]:
        self.validation_calls.append(session_id)
        if session_id == self.slow_session_id:
            self.validation_started.set()
            self.release_validation.wait(timeout=1)
            self.validation_finished.set()
        actual = self.sessions.get(session_id)
        if actual != workspace_root:
            raise RuntimeError(f"missing session {session_id}")
        return {"session_id": session_id, "workspace_root": actual}

    async def create_session(self, **kwargs: Any) -> SimpleNamespace:
        workspace_root = str(kwargs["workspace_root"])
        self.create_calls.append(workspace_root)
        session_id = f"created-{len(self.create_calls)}"
        self.sessions[session_id] = workspace_root
        return SimpleNamespace(session_id=session_id)


def _agent(
    tmp_path: Path, agent_id: str, *, version: str = "v1"
) -> AgentWorkspaceConfig:
    workspace = tmp_path / f"{agent_id}-{version}"
    workspace.mkdir()
    return AgentWorkspaceConfig(agent_id=agent_id, workspace_root=workspace)


def _request(agent_id: str) -> SessionBindingRequest:
    conversation_id = f"conv-{agent_id}"
    message = InboundMessage(
        channel_name="web_relay",
        text="hello",
        external_user_id="user",
        external_chat_id=conversation_id,
        is_group=False,
        agent_id=agent_id,
    )
    return SessionBindingRequest(
        session_key=f"web_relay:{conversation_id}:{agent_id}",
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id=conversation_id,
        ),
        message=message,
    )


def _bind_existing(
    binder: GatewaySessionBinder,
    kernel: _SlowValidationKernel,
    catalog: LiveAgentCatalog,
    agent: AgentWorkspaceConfig,
) -> None:
    request = _request(agent.agent_id)
    session_id = f"session-{agent.agent_id}"
    kernel.sessions[session_id] = str(agent.workspace_root)
    snapshot = catalog.require(agent.agent_id)
    binder.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id=f"conv-{agent.agent_id}",
            agent_id=agent.agent_id,
            kernel_session_id=session_id,
            guard=binder.capture_write_guard(snapshot),
        ),
        snapshot,
    )


async def test_slow_workspace_validation_does_not_block_unrelated_bindings(
    tmp_path: Path,
) -> None:
    agents = tuple(
        _agent(tmp_path, agent_id) for agent_id in ("agent-a", "agent-b", "agent-c")
    )
    catalog = LiveAgentCatalog(agents)
    kernel = _SlowValidationKernel(slow_session_id="session-agent-a")
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)
    for agent in agents:
        _bind_existing(binder, kernel, catalog, agent)

    slow = asyncio.create_task(
        binder.resolve(_request("agent-a"), catalog.require("agent-a"))
    )
    try:
        await asyncio.wait_for(
            asyncio.to_thread(kernel.validation_started.wait), timeout=2
        )
        assert not kernel.validation_finished.is_set()
        fast = await asyncio.wait_for(
            binder.resolve(_request("agent-b"), catalog.require("agent-b")),
            timeout=0.5,
        )
        binder.invalidate_stale("agent-c", current_revision=999)

        assert fast.kernel_session_id == "session-agent-b"
        retained = binder.lookup(_request("agent-c").session_key)
        assert retained is not None
        assert retained.kernel_session_id == "session-agent-c"
        assert not kernel.validation_finished.is_set()
    finally:
        kernel.release_validation.set()
        await slow


async def test_publish_during_slow_validation_never_republishes_stale_binding(
    tmp_path: Path,
) -> None:
    old_agent = _agent(tmp_path, "agent-a")
    catalog = LiveAgentCatalog((old_agent,))
    kernel = _SlowValidationKernel(slow_session_id="session-agent-a")
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)
    _bind_existing(binder, kernel, catalog, old_agent)
    request = _request("agent-a")

    resolving = asyncio.create_task(binder.resolve(request, catalog.require("agent-a")))
    await asyncio.wait_for(asyncio.to_thread(kernel.validation_started.wait), timeout=2)
    assert not kernel.validation_finished.is_set()
    current = catalog.publish(_agent(tmp_path, "agent-a", version="v2"))
    binder.invalidate_stale("agent-a", current_revision=current.revision)
    retained = binder.lookup(request.session_key)
    assert retained is not None
    assert retained.kernel_session_id == "session-agent-a"

    kernel.release_validation.set()
    old_result = await resolving

    assert old_result.kernel_session_id == "session-agent-a"
    retained = binder.lookup(request.session_key)
    assert retained is not None
    assert retained.kernel_session_id == "session-agent-a"
    new_result = await binder.resolve(request, current)
    assert new_result.kernel_session_id == "created-1"
    assert binder.lookup(request.session_key) == new_result
    assert kernel.create_calls == [str(current.config.workspace_root)]


async def test_stable_reuse_validates_once_per_binder_process_ownership(
    tmp_path: Path,
) -> None:
    """Stable reuse is O(1), while a restarted binder revalidates persisted state."""

    agent = _agent(tmp_path, "agent-a")
    catalog = LiveAgentCatalog((agent,))
    kernel = _SlowValidationKernel(slow_session_id="never-slow")
    db_path = tmp_path / "bindings.sqlite3"
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel, db_path=db_path)
    _bind_existing(binder, kernel, catalog, agent)
    request = _request("agent-a")
    snapshot = catalog.require("agent-a")
    first = await binder.resolve(request, snapshot)
    second = await binder.resolve(request, snapshot)

    assert first.kernel_session_id == second.kernel_session_id == "session-agent-a"
    assert kernel.validation_calls == ["session-agent-a"]

    restarted = GatewaySessionBinder(catalog=catalog, kernel=kernel, db_path=db_path)
    resumed = await restarted.resolve(request, snapshot)

    assert resumed.kernel_session_id == "session-agent-a"
    assert kernel.validation_calls == ["session-agent-a", "session-agent-a"]
