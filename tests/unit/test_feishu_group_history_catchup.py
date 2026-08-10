"""Feishu group history catch-up behavior before a bot trigger."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import (
    FeishuAPIError,
    FeishuMention,
    FeishuMessageEvent,
)
from personal_assistant.gateway.group_context_store import GroupContextStore


def _group_event(
    *,
    text: str,
    message_id: str,
    sender_open_id: str = "ou_user",
    mentions: list[FeishuMention] | None = None,
    source_timestamp: datetime | None = None,
) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        sender_display_name="Alice",
        chat_id="oc_group",
        chat_type="group",
        message_id=message_id,
        is_group=True,
        mentions=mentions or [],
        raw_text=text,
        mention_only=bool(mentions),
        source_timestamp=source_timestamp,
    )


def _adapter(client_class: MagicMock) -> tuple[FeishuAdapter, MagicMock, MagicMock]:
    client = client_class.return_value
    on_inbound = MagicMock()
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        bot_open_id="ou_bot",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(on_inbound)
    return adapter, client, on_inbound


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_trigger_catches_up_visible_background_before_current_message(
    client_class: MagicMock,
) -> None:
    adapter, client, on_inbound = _adapter(client_class)
    mention = FeishuMention("ou_bot", "plato", "@_user_1")
    background_time = datetime(2026, 8, 10, 1, 17, tzinfo=timezone.utc)
    background = _group_event(
        text="你会数学吗",
        message_id="background",
        source_timestamp=background_time,
    )
    trigger = _group_event(text="@plato", message_id="trigger", mentions=[mention])
    client.fetch_group_messages.return_value = [background, trigger]

    adapter._handle_message(trigger)

    history_message = on_inbound.call_args_list[0].args[0]
    trigger_message = on_inbound.call_args_list[1].args[0]
    assert history_message.text == "你会数学吗"
    assert history_message.metadata["sync_only"] is True
    assert history_message.metadata["feishu_delivery_source"] == "history_catchup"
    assert history_message.source_timestamp == background_time
    assert trigger_message.text == "@plato"
    assert trigger_message.metadata["mentioned_agent_ids"] == ["plato"]


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_catchup_only_delivers_user_messages_after_latest_bot_reply(
    client_class: MagicMock,
) -> None:
    adapter, client, on_inbound = _adapter(client_class)
    mention = FeishuMention("ou_bot", "plato", "@_user_1")
    trigger = _group_event(text="@plato", message_id="trigger", mentions=[mention])
    client.fetch_group_messages.return_value = [
        _group_event(text="old question", message_id="old"),
        _group_event(text="bot reply", message_id="bot", sender_open_id="ou_bot"),
        _group_event(text="app echo", message_id="echo", sender_open_id="cli_a"),
        _group_event(text="new question", message_id="new"),
        trigger,
    ]

    adapter._handle_message(trigger)

    assert [call.args[0].text for call in on_inbound.call_args_list] == [
        "new question",
        "@plato",
    ]


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_history_permission_failure_does_not_drop_current_trigger(
    client_class: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, client, on_inbound = _adapter(client_class)
    client.fetch_group_messages.side_effect = FeishuAPIError(
        "missing im:message.group_msg",
        code=230027,
    )
    trigger = _group_event(
        text="@plato",
        message_id="trigger",
        mentions=[FeishuMention("ou_bot", "plato", "@_user_1")],
    )

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.channels.feishu.adapter",
    ):
        adapter._handle_message(trigger)

    on_inbound.assert_called_once()
    assert on_inbound.call_args.args[0].metadata["mentioned_agent_ids"] == ["plato"]
    assert "ordinary group messages may be missing" in caplog.text
