"""Channel registry lifecycle and session key routing tests."""

from __future__ import annotations

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    InboundIngress,
    InboundMessage,
    OutboundMessage,
)
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.session_keys import build_session_key


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started_with = None
        self.stopped = 0
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound):
        self.started_with = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        self.stopped += 1


def test_channel_registry_and_bootstrap_manage_adapter_lifecycle() -> None:
    channel_a = _FakeChannel("web")
    channel_b = _FakeChannel("qq")
    registry = ChannelRegistry((channel_a, channel_b))
    seen: list[InboundMessage] = []

    started = start_channels(registry, seen.append)
    stopped = stop_channels(registry)

    assert started == ("web", "qq")
    assert channel_a.started_with is not None
    assert channel_b.started_with is not None
    assert stopped == ("qq", "web")
    assert channel_a.stopped == 1
    assert channel_b.stopped == 1


def test_build_session_key_uses_chat_id_for_groups_and_direct_messages() -> None:
    group_message = InboundMessage(
        channel_name="web",
        text="hello group",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=True,
    )
    direct_message = InboundMessage(
        channel_name="web",
        text="hello dm",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    assert build_session_key(group_message, agent_id="agent-a") == "web:chat-1:agent-a"
    assert build_session_key(direct_message, agent_id="agent-a") == "web:chat-1:agent-a"


def test_build_session_key_uses_shared_external_conversation_identity() -> None:
    shadow_relay_message = InboundMessage(
        channel_name="web_relay",
        text="continue from IM shadow",
        external_user_id="im-user-1",
        external_chat_id="im-conv-1",
        is_group=False,
        agent_id="agent-a",
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="feishu:cli_a:dm:ou_user1",
                agent_id="agent-a",
                conversation_type="direct",
                trigger_source="im",
            )
        ),
    )
    feishu_message = InboundMessage(
        channel_name="feishu:agent-a",
        text="continue from feishu",
        external_user_id="ou_user1",
        external_chat_id="feishu:cli_a:dm:ou_user1",
        is_group=False,
        agent_id="agent-a",
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="feishu:cli_a:dm:ou_user1",
                agent_id="agent-a",
                conversation_type="direct",
                trigger_source="feishu",
            )
        ),
    )

    expected = "feishu:feishu:cli_a:dm:ou_user1:agent-a"
    assert build_session_key(shadow_relay_message, agent_id="agent-a") == expected
    assert build_session_key(feishu_message, agent_id="agent-a") == expected
