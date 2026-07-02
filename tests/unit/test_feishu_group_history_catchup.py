"""Tests for Feishu group history catch-up before @Bot triggers."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.feishu_adapter import FeishuAdapter
from personal_assistant.channels.feishu_client import (
    FeishuAPIError,
    FeishuMessageEvent,
    FeishuMention,
)
from personal_assistant.gateway.group_context_store import GroupContextStore


def _make_group_event(
    *,
    text: str,
    message_id: str,
    sender_open_id: str = "ou_user1",
    mentions: list[FeishuMention] | None = None,
) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        sender_display_name="Alice",
        chat_id="oc_grp1",
        chat_type="group",
        message_id=message_id,
        is_group=True,
        mentions=mentions or [],
        raw_text=text,
        mention_only=bool(mentions) and text.startswith("@"),
    )


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_at_bot_catches_up_ordinary_history_before_trigger(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc_cls.return_value = mock_fc
    mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
    background = _make_group_event(text="你会数学吗", message_id="om_bg")
    current = _make_group_event(
        text="@plato",
        message_id="om_at",
        mentions=[mention],
    )
    mock_fc.fetch_group_messages.return_value = [background, current]

    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    adapter._handle_message(current)

    assert on_inbound.call_count == 2
    history_msg: InboundMessage = on_inbound.call_args_list[0].args[0]
    trigger_msg: InboundMessage = on_inbound.call_args_list[1].args[0]
    assert history_msg.text == "你会数学吗"
    assert history_msg.metadata["sync_only"] is True
    assert history_msg.metadata["feishu_delivery_source"] == "history_catchup"
    assert trigger_msg.text == "@plato"
    assert trigger_msg.metadata["mentioned_agent_ids"] == ["plato"]
    assert "sync_only" not in trigger_msg.metadata


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_history_catchup_skips_bot_self_messages(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc_cls.return_value = mock_fc
    mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
    bot_reply = _make_group_event(
        text="我在。看到了你的测试消息。",
        message_id="om_bot",
        sender_open_id="cli_a",
    )
    background = _make_group_event(text="你会数学吗", message_id="om_bg")
    current = _make_group_event(
        text="@plato",
        message_id="om_at",
        mentions=[mention],
    )
    mock_fc.fetch_group_messages.return_value = [bot_reply, background, current]

    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    adapter._handle_message(current)

    delivered = [call.args[0].text for call in on_inbound.call_args_list]
    assert delivered == ["你会数学吗", "@plato"]


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_history_catchup_only_keeps_messages_after_last_bot_reply(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc_cls.return_value = mock_fc
    mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
    old_background = _make_group_event(text="旧问题", message_id="om_old")
    bot_reply = _make_group_event(
        text="旧回复",
        message_id="om_bot",
        sender_open_id="cli_a",
    )
    new_background = _make_group_event(text="你会数学吗", message_id="om_bg")
    current = _make_group_event(
        text="@plato",
        message_id="om_at",
        mentions=[mention],
    )
    mock_fc.fetch_group_messages.return_value = [
        old_background,
        bot_reply,
        new_background,
        current,
    ]

    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    adapter._handle_message(current)

    delivered = [call.args[0].text for call in on_inbound.call_args_list]
    assert delivered == ["你会数学吗", "@plato"]


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_history_permission_failure_warns_but_delivers_current_trigger(
    mock_fc_cls: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_fc = MagicMock()
    mock_fc.fetch_group_messages.side_effect = FeishuAPIError(
        "missing im:message.group_msg",
        code=230027,
    )
    mock_fc_cls.return_value = mock_fc
    mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
    current = _make_group_event(
        text="@plato",
        message_id="om_at",
        mentions=[mention],
    )

    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.channels.feishu_adapter",
    ):
        adapter._handle_message(current)

    on_inbound.assert_called_once()
    trigger_msg: InboundMessage = on_inbound.call_args.args[0]
    assert trigger_msg.metadata["mentioned_agent_ids"] == ["plato"]
    assert "ordinary group messages may be missing" in caplog.text
