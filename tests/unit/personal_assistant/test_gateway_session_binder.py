"""Public behavior tests for Gateway session binding ownership."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import (
    ConversationBindingRequest,
    GatewaySessionBinder,
    SessionBindingRequest,
    build_session_log_path_provider,
)
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    SessionBindingStore,
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


async def test_resolve_reuses_matching_binding_and_refreshes_reply_context(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    kernel = _Kernel()
    kernel.sessions["persisted-session"] = str(agent.workspace_root)
    store = SessionBindingStore()
    store.bind(
        session_key="web_relay:conv-1:agent-a",
        kernel_session_id="persisted-session",
        reply_context=ReplyContext(channel_name="web_relay", target_chat_id="old"),
    )
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)

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
    store = SessionBindingStore()
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)

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
    store = SessionBindingStore()
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)
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
    store = PersistentSessionBindingStore(db_path=tmp_path / "bindings.sqlite3")
    reply = ReplyContext(channel_name="web_relay", target_chat_id="conv")
    for index, agent in enumerate(agents):
        store.bind(
            session_key=f"web_relay:conv-{index}:{agent.agent_id}",
            kernel_session_id=f"session-{index}",
            reply_context=reply,
        )
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=object())

    binder.invalidate_stale("team_a", current_revision=999)
    binder.invalidate_stale("team%a", current_revision=999)

    assert store.get("web_relay:conv-0:team_a") is not None
    assert store.get("web_relay:conv-2:team%a") is not None
    assert store.get("web_relay:conv-1:teamXa") is not None
    assert store.get("web_relay:conv-3:teamXXa") is not None


def test_persistent_canonical_lookup_treats_channel_and_agent_as_literals(
    tmp_path: Path,
) -> None:
    target = _agent(tmp_path, title="Target", agent_id="team_a")
    catalog = LiveAgentCatalog((target,))
    store = PersistentSessionBindingStore(db_path=tmp_path / "bindings.sqlite3")
    reply = ReplyContext(channel_name="web_relay", target_chat_id="target")
    store.bind(
        session_key="webXrelay:decoy:teamXa",
        kernel_session_id="session-decoy",
        reply_context=reply,
    )
    expected = store.bind(
        session_key="web_relay:target:team_a",
        kernel_session_id="session-target",
        reply_context=reply,
    )
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=object())

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
        repository=SessionBindingStore(),
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


def test_conversation_bind_publishes_only_successful_projection_replacements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    store = PersistentSessionBindingStore(db_path=tmp_path / "bindings.sqlite3")
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=_Kernel())
    snapshot = catalog.require("agent-a")
    provider = build_session_log_path_provider(
        session_binder=binder,
        channel_name="web_relay",
        workspace_config_dirname=".nanoassistant",
    )

    def bind(kernel_session_id: str):
        return binder.bind_conversation(
            ConversationBindingRequest(
                channel_name="web_relay",
                conversation_id="conv-projection",
                agent_id="agent-a",
                kernel_session_id=kernel_session_id,
                guard=binder.capture_write_guard(snapshot),
            ),
            snapshot,
        )

    assert bind("session-a").status == "bound"
    assert provider("agent-a", "conv-projection") == str(
        agent.workspace_root / ".nanoassistant" / "sessions" / "session-a.jsonl"
    )
    second = bind("session-b")
    assert second.status == "bound"
    assert provider("agent-a", "conv-projection") == str(
        agent.workspace_root / ".nanoassistant" / "sessions" / "session-b.jsonl"
    )

    def fail_bind(**_: Any) -> None:
        raise OSError("injected durable bind failure")

    monkeypatch.setattr(store, "bind", fail_bind)
    with pytest.raises(OSError, match="injected durable bind failure"):
        bind("session-c")

    assert store.get("web_relay:conv-projection:agent-a") == second.binding
    assert provider("agent-a", "conv-projection") == str(
        agent.workspace_root / ".nanoassistant" / "sessions" / "session-b.jsonl"
    )
    assert (
        binder.capture_session_provenance("session-b", expected_agent_id="agent-a")
        is not None
    )
    assert (
        binder.capture_session_provenance("session-c", expected_agent_id="agent-a")
        is None
    )


def test_reverse_and_canonical_lookups_only_expose_current_bindings(
    tmp_path: Path,
) -> None:
    agent = _agent(tmp_path)
    catalog = LiveAgentCatalog((agent,))
    store = SessionBindingStore()
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=_Kernel())
    snapshot = catalog.require("agent-a")

    def bind(conversation_id: str, kernel_session_id: str):
        return binder.bind_conversation(
            ConversationBindingRequest(
                channel_name="web_relay",
                conversation_id=conversation_id,
                agent_id="agent-a",
                kernel_session_id=kernel_session_id,
                guard=binder.capture_write_guard(snapshot),
            ),
            snapshot,
        )

    first = bind("conv-first", "session-first")
    second = bind("conv-second", "session-second")

    assert first.status == second.status == "bound"
    assert binder.find_by_kernel_session_id("session-second") == second.binding
    assert (
        binder.find_canonical_direct(channel_name="web_relay", agent_id="agent-a")
        == first.binding
    )
