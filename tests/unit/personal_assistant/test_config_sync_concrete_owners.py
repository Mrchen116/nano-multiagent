"""Config sync integration coverage using concrete catalog and binder owners."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.agent_config_sync import IMAgentConfigSync
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import SessionBindingStore

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


def test_v1_to_v2_publish_invalidates_binding_and_next_resolve_uses_v2(tmp_path) -> None:
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
