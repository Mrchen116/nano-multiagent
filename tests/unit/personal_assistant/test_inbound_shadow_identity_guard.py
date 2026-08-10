"""Typed identity guards for IM-originated WebRelay inbound messages."""

from __future__ import annotations

import asyncio

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    IMRelayIngress,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.inbound_models import (
    GatewayShadowState,
    ShadowConversationRef,
)
from personal_assistant.gateway.session_keys import SessionBindingStore
from tests.helpers.inbound_pipeline import build_inbound_pipeline

from ._pipeline_helpers import _FakeChannel, _FakeKernel


class _ShadowSync:
    def __init__(self) -> None:
        self.calls: list[InboundMessage] = []

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> GatewayShadowState:
        self.calls.append(message)
        return GatewayShadowState(
            saga_id="saga-1",
            ref=ShadowConversationRef(
                conversation_id=f"shadow-{agent_id}",
                im_message_id="message-1",
            ),
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
    message = InboundMessage(
        channel_name="web_relay",
        external_user_id="user-1",
        external_chat_id="conversation-1",
        text="hello",
        is_group=False,
        agent_id="agent-a",
        ingress=InboundIngress(
            im_relay=IMRelayIngress(
                relay_task_id="relay-1",
                idempotency_key="idem-1",
                im_message_id="message-1",
            ),
            external_conversation=ExternalConversationIdentity(
                external_source="im",
                external_chat_id="conversation-1",
                agent_id="agent-a",
                trigger_source="im",
            ),
        ),
    )

    result = asyncio.run(pipeline.handle_inbound(message))

    assert result is not None
    assert sync.calls == []
    assert channel.sent[0].target_chat_id == "conversation-1"
