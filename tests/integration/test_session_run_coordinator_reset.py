"""Real Kernel coverage for Gateway exact-session reset isolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage
from agent.sdk import LLMConfig, PermissionDecision, build_kernel
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    NewSessionRequest,
    RoutedInbound,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import (
    SessionBindingStore,
    build_session_key,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from tests.unit.personal_assistant._pipeline_helpers import _FakeChannel
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


async def _allow_all(_tool: str, _input: Any, _context: Any) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


class _ContextProbeClient:
    """Return whether each model request includes the old-session sentinel."""

    def __init__(self, sentinel: str) -> None:
        self.sentinel = sentinel
        self.requests: list[Any] = []

    async def generate(self, request: Any):
        self.requests.append(request)
        context = " ".join(str(message.content) for message in request.messages)
        yield LLMMessage(
            role="assistant",
            content="old-context" if self.sentinel in context else "fresh-context",
            finish_reason="stop",
        )


def _request(message, catalog: LiveAgentCatalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


@pytest.mark.asyncio
async def test_exact_new_binds_following_turn_to_fresh_real_kernel_transcript(
    tmp_path: Path,
) -> None:
    """The fresh Gateway binding must not replay the prior Kernel conversation."""

    sentinel = "old-session-secret"
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    client = _ContextProbeClient(sentinel)
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),)
    )
    store = SessionBindingStore()
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        group_context_store=GroupContextStore(tmp_path / "group.sqlite3"),
    )
    try:
        first_message = inbound(chat_id="chat-a", text=sentinel)
        first = await coordinator.dispatch(_request(first_message, catalog))
        agent = catalog.require("agent-a")
        reset_message = inbound(chat_id="chat-a", text="/new")
        reset = await coordinator.new_session(
            NewSessionRequest(
                routed=RoutedInbound(message=reset_message),
                agent=agent,
                session_key=build_session_key(reset_message, agent_id=agent.agent_id),
                operation_id="relay:new-1",
            )
        )
        second = await coordinator.dispatch(
            _request(
                inbound(chat_id="chat-a", text="what is the prior secret?"), catalog
            )
        )

        assert reset.reply_text == "已开始新会话。"
        assert reset.kernel_session_id != first.kernel_session_id
        assert second.kernel_session_id == reset.kernel_session_id
        assert second.reply_text == "fresh-context"
        assert len(client.requests) == 2
        second_context = " ".join(
            str(message.content) for message in client.requests[-1].messages
        )
        assert sentinel not in second_context
    finally:
        await kernel.aclose()
