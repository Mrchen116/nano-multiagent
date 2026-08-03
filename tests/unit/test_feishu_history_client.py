"""Provider-boundary tests for Feishu group history."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("lark_oapi")

from lark_oapi.api.im.v1 import Mention, Message, MessageBody, Sender

from personal_assistant.channels.feishu.client import (
    FeishuClient,
    _parse_feishu_history_message,
)


def test_history_parser_reads_rest_sender_body_and_mentions() -> None:
    sender = Sender()
    sender.id = "ou_user"
    sender.id_type = "open_id"
    sender.sender_name = "Alice"
    mention = Mention()
    mention.key = "@_user_1"
    mention.id = "ou_bot"
    mention.id_type = "open_id"
    mention.name = "nano"
    body = MessageBody()
    body.content = '{"text":"@_user_1 你好"}'
    message = Message()
    message.message_id = "message-1"
    message.msg_type = "text"
    message.body = body
    message.sender = sender
    message.mentions = [mention]

    event = _parse_feishu_history_message(message, chat_id="oc_group")

    assert event.text == "@nano 你好"
    assert event.sender_open_id == "ou_user"
    assert event.sender_display_name == "Alice"
    assert [(item.open_id, item.name) for item in event.mentions] == [
        ("ou_bot", "nano")
    ]


def test_fetch_group_messages_filters_empty_history_text() -> None:
    empty = MagicMock()
    empty.message_id = "empty"
    empty.msg_type = "text"
    empty.content = '{"text":"   "}'
    empty.body.content = ""
    empty.sender.sender_id.open_id = "ou_user"
    empty.mentions = []
    visible = MagicMock()
    visible.message_id = "visible"
    visible.msg_type = "text"
    visible.content = ""
    visible.body.content = '{"text":"background question"}'
    visible.sender.sender_id.open_id = "ou_user"
    visible.mentions = []
    response = MagicMock()
    response.success.return_value = True
    response.data.items = [empty, visible]
    rest = MagicMock()
    rest.im.v1.message.list.return_value = response
    client = FeishuClient(app_id="cli_a", app_secret="secret")
    client._rest_client = rest

    events = client.fetch_group_messages(chat_id="oc_group")

    assert [(event.message_id, event.text) for event in events] == [
        ("visible", "background question")
    ]
