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
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import SessionBindingStore


class _SlowValidationKernel:
    def __init__(self, *, slow_session_id: str) -> None:
        self.slow_session_id = slow_session_id
        self.validation_started = ThreadEvent()
        self.validation_finished = ThreadEvent()
        self.release_validation = ThreadEvent()
        self.sessions: dict[str, str] = {}
        self.create_calls: list[str] = []

    def get_session(self, *, session_id: str, workspace_root: str) -> dict[str, str]:
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


def _agent(tmp_path: Path, agent_id: str, *, version: str = "v1") -> AgentWorkspaceConfig:
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
    store: SessionBindingStore,
    kernel: _SlowValidationKernel,
    agent: AgentWorkspaceConfig,
) -> None:
    request = _request(agent.agent_id)
    session_id = f"session-{agent.agent_id}"
    kernel.sessions[session_id] = str(agent.workspace_root)
    store.bind(
        session_key=request.session_key,
        kernel_session_id=session_id,
        reply_context=request.reply_context,
    )


async def test_slow_workspace_validation_does_not_block_unrelated_bindings(
    tmp_path: Path,
) -> None:
    agents = tuple(
        _agent(tmp_path, agent_id)
        for agent_id in ("agent-a", "agent-b", "agent-c")
    )
    catalog = LiveAgentCatalog(agents)
    store = SessionBindingStore()
    kernel = _SlowValidationKernel(slow_session_id="session-agent-a")
    for agent in agents:
        _bind_existing(store, kernel, agent)
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)

    slow = asyncio.create_task(
        binder.resolve(_request("agent-a"), catalog.require("agent-a"))
    )
    try:
        await asyncio.wait_for(asyncio.to_thread(kernel.validation_started.wait), timeout=2)
        assert not kernel.validation_finished.is_set()
        fast = await asyncio.wait_for(
            binder.resolve(_request("agent-b"), catalog.require("agent-b")),
            timeout=0.5,
        )
        binder.invalidate_stale("agent-c", current_revision=999)

        assert fast.kernel_session_id == "session-agent-b"
        assert binder.lookup(_request("agent-c").session_key) is None
        assert not kernel.validation_finished.is_set()
    finally:
        kernel.release_validation.set()
        await slow


async def test_publish_during_slow_validation_never_republishes_stale_binding(
    tmp_path: Path,
) -> None:
    old_agent = _agent(tmp_path, "agent-a")
    catalog = LiveAgentCatalog((old_agent,))
    store = SessionBindingStore()
    kernel = _SlowValidationKernel(slow_session_id="session-agent-a")
    _bind_existing(store, kernel, old_agent)
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)
    request = _request("agent-a")

    resolving = asyncio.create_task(binder.resolve(request, catalog.require("agent-a")))
    await asyncio.wait_for(asyncio.to_thread(kernel.validation_started.wait), timeout=2)
    assert not kernel.validation_finished.is_set()
    current = catalog.publish(_agent(tmp_path, "agent-a", version="v2"))
    binder.invalidate_stale("agent-a", current_revision=current.revision)
    assert binder.lookup(request.session_key) is None

    kernel.release_validation.set()
    old_result = await resolving

    assert old_result.kernel_session_id == "session-agent-a"
    assert binder.lookup(request.session_key) is None
    new_result = await binder.resolve(request, current)
    assert binder.lookup(request.session_key) == new_result
    assert kernel.create_calls == [str(current.config.workspace_root)]
