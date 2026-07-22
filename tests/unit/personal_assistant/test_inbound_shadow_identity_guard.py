"""Typed identity guards for IM-originated WebRelay inbound messages."""

from __future__ import annotations

import asyncio

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.runtime_protocol import (
    ExternalConversationIdentity,
    RuntimeProtocolFacts,
    ShadowConversationRef,
    attach_runtime_protocol,
)
from personal_assistant.gateway.session_keys import SessionBindingStore
from tests.helpers.inbound_pipeline import build_inbound_pipeline

from ._pipeline_helpers import _FakeChannel, _FakeKernel


class _ShadowSync:
    def __init__(self) -> None:
        self.calls: list[InboundMessage] = []

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> ShadowConversationRef:
        self.calls.append(message)
        return ShadowConversationRef(
            conversation_id=f"shadow-{agent_id}",
            im_message_id="message-1",
        )


def test_im_originated_typed_identity_skips_external_shadow_sync(tmp_path) -> None:
    """WebRelay already represents the canonical IM message and must not POST it again."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    sync = _ShadowSync()
    channel = _FakeChannel("web_relay")
    pipeline = build_inbound_pipeline(
        kernel=_FakeKernel(),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),),
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        shadow_sync=sync,
    )
    message = attach_runtime_protocol(
        InboundMessage(
            channel_name="web_relay",
            external_user_id="user-1",
            external_chat_id="conversation-1",
            text="hello",
            is_group=False,
            agent_id="agent-a",
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="im",
                external_chat_id="conversation-1",
                agent_id="agent-a",
                trigger_source="im",
            )
        ),
    )

    result = asyncio.run(pipeline.handle_inbound(message))

    assert result is not None
    assert sync.calls == []
    assert channel.sent[0].target_chat_id == "conversation-1"
