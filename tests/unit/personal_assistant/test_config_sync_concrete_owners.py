"""Config sync integration coverage using concrete catalog and binder owners."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.gateway import agent_config_sync as config_sync_module

from ._gateway_runtime_test_utils import make_config


class _Kernel:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.sessions: dict[str, str] = {}

    async def create_session(self, **kwargs):
        self.create_calls.append(kwargs)
        session_id = f"session-{len(self.create_calls)}"
        self.sessions[session_id] = str(kwargs["workspace_root"])
        return SimpleNamespace(session_id=session_id)

    def get_session(self, *, session_id: str, workspace_root: str):
        if self.sessions.get(session_id) != workspace_root:
            raise RuntimeError("session workspace mismatch")
        return {"session_id": session_id, "workspace_root": workspace_root}


def test_v1_to_v2_publish_invalidates_binding_and_next_resolve_uses_v2(
    tmp_path,
) -> None:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    initial = AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace)
    config_root = tmp_path / "config-root"
    config_root.mkdir()
    config = replace(
        make_config(config_root),
        agents=(initial,),
        source_path=tmp_path / "config.yaml",
    )
    catalog = LiveAgentCatalog(config.agents)
    kernel = _Kernel()
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
    )
    version = 0

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "agent_id": "agent-a",
                "display_name": f"Agent v{version}",
                "profile_version": version,
                "custom_prompt": f"prompt-v{version}",
                "skills": [],
                "tool_allowlist": [],
                "features": {},
            },
        )

    client = IMAgentConfigSync(
        base_url="http://im.local",
        token=None,
        agent_catalog=catalog,
        session_binder=binder,
        local_config=config,
        client=httpx.Client(
            transport=httpx.MockTransport(_handler), base_url="http://im.local"
        ),
        max_attempts=1,
    )
    message = InboundMessage(
        channel_name="web_relay",
        external_user_id="user-1",
        external_chat_id="conversation-1",
        text="hello",
        is_group=False,
        agent_id="agent-a",
    )
    request = SessionBindingRequest(
        session_key="web_relay:conversation-1:agent-a",
        reply_context=ReplyContext(
            channel_name="web_relay", target_chat_id="conversation-1"
        ),
        message=message,
        gateway_internal_port=8089,
    )

    version = 1
    client.sync_agent(agent_id="agent-a", profile_version=1)
    v1 = catalog.require("agent-a")
    old_binding = asyncio.run(binder.resolve(request, v1))

    version = 2
    client.sync_agent(agent_id="agent-a", profile_version=2)
    v2 = catalog.require("agent-a")

    assert v2.revision > v1.revision
    assert v2.config.custom_prompt == "prompt-v2"
    assert binder.lookup(request.session_key) is None

    new_binding = asyncio.run(binder.resolve(request, v2))
    assert new_binding.kernel_session_id != old_binding.kernel_session_id
    prompt = kernel.create_calls[-1]["prompt"]
    assert prompt.custom[0].text.endswith("prompt-v2")


def _unchanged_payload(workspace) -> dict[str, object]:
    return {
        "agent_id": "agent-a",
        "display_name": "Agent A",
        "profile_version": 7,
        "workspace_root": str(workspace),
        "skills": ["skill-a"],
        "tool_allowlist": ["read"],
        "system_prompt": "system-a",
        "group_reply_policy": "MENTION",
        "default_model": "kimiCoding:K2.6",
        "features": {"heartbeat": True},
        "custom_prompt": "custom-a",
        "heartbeat": {"every": "30m"},
    }


def test_unchanged_sync_and_reconcile_do_not_rewrite_or_republish(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        title="Agent A",
        skills=("skill-a",),
        tool_allowlist=("read",),
        system_prompt="system-a",
        group_reply_policy="MENTION",
        default_model="kimiCoding:K2.6",
        features={"heartbeat": True},
        custom_prompt="custom-a",
        heartbeat_every="30m",
    )
    root = tmp_path / "config-root"
    root.mkdir()
    config = replace(
        make_config(root), agents=(agent,), source_path=tmp_path / "config.yaml"
    )
    catalog = LiveAgentCatalog(config.agents)
    binder = GatewaySessionBinder(
        catalog=catalog, repository=SessionBindingStore(), kernel=object()
    )
    saves: list[object] = []
    monkeypatch.setattr(
        config_sync_module,
        "save_local_config",
        lambda local_config, _path: saves.append(local_config),
    )
    client = IMAgentConfigSync(
        base_url="http://im.local",
        token=None,
        agent_catalog=catalog,
        session_binder=binder,
        local_config=config,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json=_unchanged_payload(workspace))
            ),
            base_url="http://im.local",
        ),
        max_attempts=1,
    )
    revision = catalog.require("agent-a").revision

    client.sync_agent(agent_id="agent-a", profile_version=7)
    client.reconcile_all_agents(memory_versions={"agent-a": 7})

    assert saves == []
    assert catalog.require("agent-a").revision == revision


def test_local_and_live_differences_are_compared_independently(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    local = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=workspace, title="Agent A"
    )
    root = tmp_path / "config-root"
    root.mkdir()
    config = replace(
        make_config(root), agents=(local,), source_path=tmp_path / "config.yaml"
    )
    catalog = LiveAgentCatalog(config.agents)
    live_drift = catalog.publish(replace(local, title="stale live"))
    binder = GatewaySessionBinder(
        catalog=catalog, repository=SessionBindingStore(), kernel=object()
    )
    saves: list[object] = []
    monkeypatch.setattr(
        config_sync_module,
        "save_local_config",
        lambda local_config, _path: saves.append(local_config),
    )
    payload = {
        **_unchanged_payload(workspace),
        "skills": [],
        "tool_allowlist": [],
        "system_prompt": "",
        "group_reply_policy": None,
        "default_model": None,
        "features": {},
        "custom_prompt": None,
        "heartbeat": None,
    }
    client = IMAgentConfigSync(
        base_url="http://im.local",
        token=None,
        agent_catalog=catalog,
        session_binder=binder,
        local_config=config,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json=payload)
            ),
            base_url="http://im.local",
        ),
        max_attempts=1,
    )

    client.sync_agent(agent_id="agent-a", profile_version=7)

    assert saves == []
    assert catalog.require("agent-a").revision > live_drift.revision
    assert catalog.require("agent-a").config == local
