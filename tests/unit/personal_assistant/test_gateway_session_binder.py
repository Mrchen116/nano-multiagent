"""Public behavior tests for Gateway session binding ownership."""

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


class _Kernel:
    def __init__(self) -> None:
        self.create_started = asyncio.Event()
        self.release_create = asyncio.Event()
        self.block_create = False
        self.create_calls: list[dict[str, Any]] = []
        self.sessions: dict[str, str] = {}

    async def create_session(self, **kwargs: Any) -> SimpleNamespace:
        self.create_calls.append(kwargs)
        self.create_started.set()
        if self.block_create:
            await self.release_create.wait()
        session_id = f"session-{len(self.create_calls)}"
        self.sessions[session_id] = str(kwargs["workspace_root"])
        return SimpleNamespace(session_id=session_id)

    def get_session(self, *, session_id: str, workspace_root: str) -> dict[str, str]:
        actual = self.sessions.get(session_id)
        if actual != str(workspace_root):
            raise RuntimeError(f"missing session {session_id}")
        return {"session_id": session_id, "workspace_root": actual}


def _agent(
    tmp_path: Path,
    *,
    title: str = "Agent A",
    agent_id: str = "agent-a",
) -> AgentWorkspaceConfig:
    workspace = tmp_path / title.replace(" ", "-")
    workspace.mkdir(exist_ok=True)
    return AgentWorkspaceConfig(
        agent_id=agent_id,
        workspace_root=workspace,
        title=title,
        skills=("skill-a",),
        tool_allowlist=("read",),
        features={"heartbeat": True},
        custom_prompt="Use concise replies.",
    )


def _message(*, conversation_id: str) -> InboundMessage:
    return InboundMessage(
        channel_name="web_relay",
        text="hello",
        external_user_id="user-1",
        external_chat_id=conversation_id,
        is_group=False,
        agent_id="agent-a",
        metadata={"conversation_id": conversation_id, "config_profile_version": 7},
    )


def _request(*, conversation_id: str) -> SessionBindingRequest:
    message = _message(conversation_id=conversation_id)
    return SessionBindingRequest(
        session_key=f"web_relay:{conversation_id}:agent-a",
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id=conversation_id,
            metadata={"conversation_id": conversation_id},
        ),
        message=message,
        gateway_internal_port=8089,
    )


def _bind_conversation(
    binder: GatewaySessionBinder,
    catalog: LiveAgentCatalog,
    *,
    conversation_id: str,
    kernel_session_id: str,
    channel_name: str = "web_relay",
    agent_id: str = "agent-a",
):
    snapshot = catalog.require(agent_id)
    return binder.bind_conversation(
        ConversationBindingRequest(
            channel_name=channel_name,
            conversation_id=conversation_id,
            agent_id=agent_id,
            kernel_session_id=kernel_session_id,
            guard=binder.capture_write_guard(snapshot),
        ),
        snapshot,
    ).binding


async def test_resolve_reuses_matching_binding_and_refreshes_reply_context(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    kernel = _Kernel()
    kernel.sessions["persisted-session"] = str(agent.workspace_root)
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)
    _bind_conversation(
        binder,
        catalog,
        conversation_id="conv-1",
        kernel_session_id="persisted-session",
    )

    binding = await binder.resolve(
        _request(conversation_id="conv-1"),
        catalog.require("agent-a"),
    )

    assert binding.kernel_session_id == "persisted-session"
    assert binding.reply_context.target_chat_id == "conv-1"
    assert binder.lookup(binding.session_key) == binding
    assert kernel.create_calls == []


async def test_resolve_creates_session_from_one_snapshot_and_persists_binding(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    kernel = _Kernel()
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)

    binding = await binder.resolve(
        _request(conversation_id="conv-create"),
        catalog.require("agent-a"),
    )

    assert binder.lookup(binding.session_key) == binding
    assert kernel.create_calls[0]["workspace_root"] == agent.workspace_root
    assert kernel.create_calls[0]["title"] == "Agent A"
    assert kernel.create_calls[0]["skills"] == ["skill-a"]
    assert kernel.create_calls[0]["enabled_tools"] == ["read"]
    assert kernel.create_calls[0]["features"] == {"heartbeat": True}
    assert kernel.create_calls[0]["metadata"]["agent_id"] == "agent-a"
    assert kernel.create_calls[0]["metadata"]["conversation_id"] == "conv-create"
    assert kernel.create_calls[0]["metadata"]["gateway_dispatch_url"].endswith(
        ":8089/internal/dispatch"
    )


async def test_publish_during_create_returns_old_session_without_stale_writeback(
    tmp_path: Path,
) -> None:
    old_agent = _agent(tmp_path, title="Agent A old")
    catalog = LiveAgentCatalog((old_agent,))
    kernel = _Kernel()
    kernel.block_create = True
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)
    old_snapshot = catalog.require("agent-a")

    resolving = asyncio.create_task(
        binder.resolve(_request(conversation_id="conv-race"), old_snapshot)
    )
    await kernel.create_started.wait()
    current = catalog.publish(_agent(tmp_path, title="Agent A new"))
    binder.invalidate_stale("agent-a", current_revision=current.revision)
    kernel.release_create.set()
    result = await resolving

    assert result.kernel_session_id == "session-1"
    assert result.reply_context.target_chat_id == "conv-race"
    assert binder.lookup(result.session_key) is None


async def test_publish_during_old_binding_reuse_retains_stable_row(
    tmp_path: Path,
) -> None:
    old_agent = _agent(tmp_path, title="Agent A old")
    catalog = LiveAgentCatalog((old_agent,))
    kernel = _Kernel()
    kernel.sessions["persisted-old-session"] = str(old_agent.workspace_root)
    request = _request(conversation_id="conv-reuse-race")
    binder = GatewaySessionBinder(catalog=catalog, kernel=kernel)
    _bind_conversation(
        binder,
        catalog,
        conversation_id="conv-reuse-race",
        kernel_session_id="persisted-old-session",
    )
    bind_started = ThreadEvent()
    release_bind = ThreadEvent()
    original_bind = binder._repository.bind  # noqa: SLF001

    def _blocking_bind(**kwargs: Any):
        if kwargs["kernel_session_id"] == "persisted-old-session":
            bind_started.set()
            if not release_bind.wait(timeout=5):
                raise TimeoutError("timed out waiting to release old binding reuse")
        return original_bind(**kwargs)

    binder._repository.bind = _blocking_bind  # type: ignore[method-assign]  # noqa: SLF001
    old_snapshot = catalog.require("agent-a")

    resolving = asyncio.create_task(
        asyncio.to_thread(
            lambda: asyncio.run(binder.resolve(request, old_snapshot)),
        )
    )
    await asyncio.wait_for(asyncio.to_thread(bind_started.wait), timeout=2)
    current = catalog.publish(_agent(tmp_path, title="Agent A new"))
    invalidation_started = ThreadEvent()

    def _invalidate() -> None:
        invalidation_started.set()
        binder.invalidate_stale("agent-a", current_revision=current.revision)

    invalidating = asyncio.create_task(asyncio.to_thread(_invalidate))
    await asyncio.wait_for(asyncio.to_thread(invalidation_started.wait), timeout=2)
    release_bind.set()

    old_result = await resolving
    await invalidating

    assert old_result.kernel_session_id == "persisted-old-session"
    assert old_result.reply_context == request.reply_context
    assert binder.lookup(request.session_key) is not None

    new_result = await binder.resolve(request, current)

    assert new_result.kernel_session_id == "session-1"
    assert new_result.kernel_session_id != old_result.kernel_session_id
    assert binder.lookup(request.session_key) == new_result
    assert len(kernel.create_calls) == 1
    assert kernel.create_calls[0]["workspace_root"] == current.config.workspace_root


def test_persistent_invalidation_keeps_agent_bindings(
    tmp_path: Path,
) -> None:
    agents = (
        _agent(tmp_path, title="Target underscore", agent_id="team_a"),
        _agent(tmp_path, title="Similar underscore", agent_id="teamXa"),
        _agent(tmp_path, title="Target percent", agent_id="team%a"),
        _agent(tmp_path, title="Similar percent", agent_id="teamXXa"),
    )
    catalog = LiveAgentCatalog(agents)
    binder = GatewaySessionBinder(
        catalog=catalog, kernel=object(), db_path=tmp_path / "bindings.sqlite3"
    )
    for index, agent in enumerate(agents):
        _bind_conversation(
            binder,
            catalog,
            conversation_id=f"conv-{index}",
            kernel_session_id=f"session-{index}",
            agent_id=agent.agent_id,
        )

    binder.invalidate_stale("team_a", current_revision=999)
    binder.invalidate_stale("team%a", current_revision=999)

    assert binder.lookup("web_relay:conv-0:team_a") is not None
    assert binder.lookup("web_relay:conv-2:team%a") is not None
    assert binder.lookup("web_relay:conv-1:teamXa") is not None
    assert binder.lookup("web_relay:conv-3:teamXXa") is not None


def test_persistent_canonical_lookup_treats_channel_and_agent_as_literals(
    tmp_path: Path,
) -> None:
    target = _agent(tmp_path, title="Target", agent_id="team_a")
    decoy = _agent(tmp_path, title="Decoy", agent_id="teamXa")
    catalog = LiveAgentCatalog((target, decoy))
    binder = GatewaySessionBinder(
        catalog=catalog, kernel=object(), db_path=tmp_path / "bindings.sqlite3"
    )
    _bind_conversation(
        binder,
        catalog,
        channel_name="webXrelay",
        conversation_id="decoy",
        agent_id="teamXa",
        kernel_session_id="session-decoy",
    )
    expected = _bind_conversation(
        binder,
        catalog,
        conversation_id="target",
        agent_id="team_a",
        kernel_session_id="session-target",
    )

    result = binder.find_canonical_direct(
        channel_name="web_relay",
        agent_id="team_a",
    )

    assert result == expected


def test_conversation_bind_rejects_guard_captured_before_publish(
    tmp_path: Path,
) -> None:
    old_agent = _agent(tmp_path, title="Agent A old")
    catalog = LiveAgentCatalog((old_agent,))
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=_Kernel(),
    )
    old_snapshot = catalog.require("agent-a")
    stale_guard = binder.capture_write_guard(old_snapshot)

    current = catalog.publish(_agent(tmp_path, title="Agent A new"))
    binder.invalidate_stale("agent-a", current_revision=current.revision)
    result = binder.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id="conv-stale",
            agent_id="agent-a",
            kernel_session_id="session-stale",
            guard=stale_guard,
        ),
        old_snapshot,
    )

    assert result.status == "stale"
    assert result.binding is None
    assert binder.lookup("web_relay:conv-stale:agent-a") is None


def test_reverse_and_canonical_lookups_only_expose_current_bindings(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    binder = GatewaySessionBinder(catalog=catalog, kernel=_Kernel())
    snapshot = catalog.require("agent-a")

    first = binder.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id="conv-first",
            agent_id="agent-a",
            kernel_session_id="session-first",
            guard=binder.capture_write_guard(snapshot),
        ),
        snapshot,
    )
    second = binder.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id="conv-second",
            agent_id="agent-a",
            kernel_session_id="session-second",
            guard=binder.capture_write_guard(snapshot),
        ),
        snapshot,
    )

    assert first.status == second.status == "bound"
    assert binder.find_by_kernel_session_id("session-second") == second.binding
    assert (
        binder.find_canonical_direct(channel_name="web_relay", agent_id="agent-a")
        == first.binding
    )


def test_binder_owns_sqlite_construction_and_restart_recovery(tmp_path: Path) -> None:
    """Callers provide a DB path and recover continuity through the binder only."""

    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    db_path = tmp_path / "bindings.sqlite3"
    first = GatewaySessionBinder(catalog=catalog, kernel=_Kernel(), db_path=db_path)
    snapshot = catalog.require("agent-a")
    bound = first.bind_conversation(
        ConversationBindingRequest(
            channel_name="web_relay",
            conversation_id="conv-restart",
            agent_id="agent-a",
            kernel_session_id="session-restart",
            guard=first.capture_write_guard(snapshot),
        ),
        snapshot,
    )

    restarted = GatewaySessionBinder(catalog=catalog, kernel=_Kernel(), db_path=db_path)

    assert bound.status == "bound"
    assert restarted.lookup("web_relay:conv-restart:agent-a") == bound.binding


def test_session_key_module_does_not_export_persistence_adapters() -> None:
    """The binder is the only public continuity persistence seam."""

    from personal_assistant.gateway import session_keys

    assert not hasattr(session_keys, "SessionBindingStore")
    assert not hasattr(session_keys, "PersistentSessionBindingStore")
    assert not hasattr(session_keys, "session_binding_store")
    assert not hasattr(session_keys, "bind_conversation_session")
