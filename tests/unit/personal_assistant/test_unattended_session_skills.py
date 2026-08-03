"""Foreground and unattended sessions use one Agent capability projection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.kernel_client import InProcessKernelClient
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import SessionBindingStore


class _Kernel:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []

    async def create_session(self, **kwargs: Any) -> SimpleNamespace:
        self.create_calls.append(kwargs)
        return SimpleNamespace(session_id=f"session-{len(self.create_calls)}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("skills", "tools", "features"),
    [
        (("restricted-a",), ("read",), {"heartbeat": True}),
        ((), (), {}),
    ],
)
async def test_foreground_and_unattended_sessions_share_agent_capabilities(
    tmp_path: Path,
    skills: tuple[str, ...],
    tools: tuple[str, ...],
    features: dict[str, bool],
) -> None:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace,
                skills=skills,
                tool_allowlist=tools,
                features=features,
                custom_prompt="Keep replies concise.",
            ),
        )
    )
    snapshot = catalog.require("agent-a")
    kernel = _Kernel()
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
    )
    message = InboundMessage(
        channel_name="web_relay",
        text="hello",
        external_user_id="user-a",
        external_chat_id="conversation-a",
        is_group=False,
        agent_id="agent-a",
        metadata={"conversation_id": "conversation-a"},
    )
    await binder.resolve(
        SessionBindingRequest(
            session_key="web_relay:conversation-a:agent-a",
            reply_context=ReplyContext(
                channel_name="web_relay",
                target_chat_id="conversation-a",
            ),
            message=message,
        ),
        snapshot,
    )
    foreground = kernel.create_calls[-1]

    await InProcessKernelClient(kernel, agent_catalog=catalog).create_agent_session(
        agent_snapshot=snapshot,
        workspace_root=str(workspace),
        product_id="personal_assistant",
        metadata=foreground["metadata"],
    )
    unattended = kernel.create_calls[-1]

    projected_fields = ("prompt", "enabled_tools", "features", "skills")
    assert {key: foreground[key] for key in projected_fields} == {
        key: unattended[key] for key in projected_fields
    }
