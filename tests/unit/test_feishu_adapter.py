"""Behavior tests for Feishu inbound normalization and routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import (
    FeishuAPIError,
    FeishuMention,
    FeishuMessageEvent,
)
from personal_assistant.gateway.group_context_store import GroupContextStore


def _event(
    *,
    text: str = "hello",
    sender_open_id: str = "ou_user1",
    sender_display_name: str | None = None,
    chat_id: str = "oc_chat123",
    chat_type: str = "p2p",
    message_id: str = "msg_001",
    mentions: list[FeishuMention] | None = None,
) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        sender_display_name=sender_display_name,
        chat_id=chat_id,
        chat_type=chat_type,
        message_id=message_id,
        is_group=chat_type == "group",
        mentions=mentions or [],
        raw_text=text,
        mention_only=False,
    )


def _adapter(**kwargs: object) -> FeishuAdapter:
    return FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        group_context_store=MagicMock(spec=GroupContextStore),
        **kwargs,
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_direct_message_maps_stable_identity_and_acknowledges(
    mock_client_class: MagicMock,
) -> None:
    client = mock_client_class.return_value
    on_inbound = MagicMock()
    adapter = _adapter()
    adapter.start(on_inbound)

    adapter._handle_message(_event(text="hi there", chat_id="oc_dm1"))

    message: InboundMessage = on_inbound.call_args.args[0]
    assert message.text == "hi there"
    assert message.agent_id == "plato"
    assert message.channel_name == "feishu:plato"
    assert message.external_user_id == "ou_user1"
    assert message.external_chat_id == "feishu:cli_a:dm:ou_user1"
    assert message.metadata["trigger_source"] == "feishu"
    assert message.external_event_identity is not None
    assert message.external_event_identity.connector_account_id == "cli_a"
    assert message.external_event_identity.provider_event_id == "msg_001"
    client.add_reaction.assert_called_once_with(
        message_id="msg_001",
        emoji_type="THINKING",
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_ack_failure_does_not_drop_direct_message(
    mock_client_class: MagicMock,
) -> None:
    client = mock_client_class.return_value
    client.add_reaction.side_effect = FeishuAPIError("reaction failed", code=99999)
    on_inbound = MagicMock()
    adapter = _adapter()
    adapter.start(on_inbound)

    adapter._handle_message(_event())

    on_inbound.assert_called_once()


@pytest.mark.parametrize(
    ("mentions", "bot_open_id", "expected_agent_mentions", "expected_ack"),
    [
        ([FeishuMention("ou_bot", "plato", "@_user_1")], "ou_bot", ["plato"], True),
        ([], "ou_bot", [], False),
        ([FeishuMention("all", "所有人", "@_all")], "ou_bot", [], False),
        ([FeishuMention("ou_other", "Bob", "@_user_1")], None, [], False),
    ],
)
@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_group_message_preserves_trigger_metadata(
    mock_client_class: MagicMock,
    mentions: list[FeishuMention],
    bot_open_id: str | None,
    expected_agent_mentions: list[str],
    expected_ack: bool,
) -> None:
    on_inbound = MagicMock()
    adapter = _adapter(bot_open_id=bot_open_id)
    adapter.start(on_inbound)

    adapter._handle_message(
        _event(
            text="@plato summarize" if expected_agent_mentions else "group update",
            chat_id="oc_group",
            chat_type="group",
            mentions=mentions,
        )
    )

    message: InboundMessage = on_inbound.call_args.args[0]
    assert message.agent_id == "plato"
    assert message.external_chat_id == "feishu:cli_a:group:oc_group"
    assert message.metadata["mentioned_agent_ids"] == expected_agent_mentions
    assert "sync_only" not in message.metadata
    if expected_ack:
        mock_client_class.return_value.add_reaction.assert_called_once()
    else:
        mock_client_class.return_value.add_reaction.assert_not_called()


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_ack_message_is_idempotent(mock_client_class: MagicMock) -> None:
    client = mock_client_class.return_value
    client.add_reaction.return_value = "reaction-1"
    adapter = _adapter()
    adapter.start(MagicMock())

    adapter.ack_message("message-1")
    adapter.ack_message("message-1")

    client.add_reaction.assert_called_once_with(
        message_id="message-1",
        emoji_type="THINKING",
    )


@pytest.mark.parametrize("agent_id", ["plato", "luban"])
@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_channel_identity_routes_to_configured_agent(
    mock_client_class: MagicMock,
    agent_id: str,
) -> None:
    on_inbound = MagicMock()
    adapter = FeishuAdapter(
        app_id=f"cli_{agent_id}",
        app_secret="secret",
        name=f"feishu:{agent_id}",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(on_inbound)

    adapter._handle_message(_event())

    assert adapter.name == f"feishu:{agent_id}"
    assert on_inbound.call_args.args[0].agent_id == agent_id
