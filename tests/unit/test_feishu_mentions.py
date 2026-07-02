"""Feishu mention parsing and mention-only delivery regressions."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.feishu_adapter import FeishuAdapter
from personal_assistant.channels.feishu_client import (
    FeishuMessageEvent,
    FeishuMention,
    _parse_feishu_event,
)
from personal_assistant.gateway.group_context_store import GroupContextStore


def _make_event(
    *,
    content: str,
    open_id: str = "ou_bot1",
    name: str = "plato-bot",
    key: str = "@_user_1",
    include_mention: bool = True,
) -> MagicMock:
    event = MagicMock()
    event.event.sender.sender_id.open_id = "ou_user1"
    event.event.message.chat_id = "oc_abc123"
    event.event.message.chat_type = "group"
    event.event.message.content = content
    event.event.message.message_id = "msg_001"
    mention = MagicMock()
    mention.id.open_id = open_id
    mention.name = name
    mention.key = key
    event.event.message.mentions = [mention] if include_mention else []
    return event


def test_parse_text_content_preserves_visible_mention() -> None:
    result = _parse_feishu_event(
        _make_event(content='{"text":"@_user_1 help me"}')
    )

    assert result.text == "@plato-bot help me"
    assert result.raw_text == "@_user_1 help me"
    assert result.mention_only is False


def test_parse_mention_only_keeps_non_empty_visible_text() -> None:
    result = _parse_feishu_event(_make_event(content='{"text":"@_user_1"}'))

    assert result.text == "@plato-bot"
    assert result.raw_text == "@_user_1"
    assert result.mention_only is True


def test_parse_at_all_keeps_visible_text() -> None:
    result = _parse_feishu_event(
        _make_event(
            content='{"text":"@_user_1 deploy freeze"}',
            open_id="all",
            name="所有人",
        )
    )

    assert result.text == "@所有人 deploy freeze"
    assert result.mention_only is False


def test_parse_live_at_all_placeholder_keeps_visible_text_without_entity() -> None:
    result = _parse_feishu_event(
        _make_event(
            content='{"text":"@_all deploy freeze"}',
            include_mention=False,
        )
    )

    assert result.text == "@所有人 deploy freeze"
    assert result.raw_text == "@_all deploy freeze"
    assert result.mentions == []
    assert result.mention_only is False


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_mention_only_delivers_non_empty_text_and_metadata(
    mock_fc_cls: MagicMock,
) -> None:
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
    event = FeishuMessageEvent(
        text="@plato",
        sender_open_id="ou_user1",
        sender_display_name=None,
        chat_id="oc_chat123",
        chat_type="group",
        message_id="msg_001",
        is_group=True,
        mentions=[mention],
        raw_text="@_user_1",
    )

    adapter._handle_message(replace(event, mention_only=True))

    msg: InboundMessage = on_inbound.call_args[0][0]
    assert msg.text == "@plato"
    assert msg.metadata["mentioned_agent_ids"] == ["plato"]
    assert msg.metadata["mention_only"] is True
