"""Tests for Feishu group history message parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import FeishuClient


def test_parse_history_message_reads_body_content() -> None:
    from personal_assistant.channels.feishu.client import (
        _parse_feishu_history_message,
    )

    message = MagicMock()
    message.message_id = "om_body"
    message.msg_type = "text"
    message.content = ""
    message.body.content = '{"text":"你会数学吗"}'
    message.sender.sender_id.open_id = "ou_user1"
    message.sender.name = "Alice"
    message.mentions = []

    event = _parse_feishu_history_message(message, chat_id="oc_group")

    assert event.message_id == "om_body"
    assert event.text == "你会数学吗"
    assert event.raw_text == "你会数学吗"
    assert event.sender_open_id == "ou_user1"


def test_fetch_group_messages_filters_empty_history_text() -> None:
    empty = MagicMock()
    empty.message_id = "om_empty"
    empty.msg_type = "text"
    empty.content = '{"text":"   "}'
    empty.body.content = ""
    empty.sender.sender_id.open_id = "ou_user1"
    empty.mentions = []

    visible = MagicMock()
    visible.message_id = "om_visible"
    visible.msg_type = "text"
    visible.content = ""
    visible.body.content = '{"text":"background question"}'
    visible.sender.sender_id.open_id = "ou_user1"
    visible.mentions = []

    response = MagicMock()
    response.success.return_value = True
    response.data.items = [empty, visible]
    mock_rest = MagicMock()
    mock_rest.im.v1.message.list.return_value = response

    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = mock_rest  # noqa: SLF001

    events = client.fetch_group_messages(chat_id="oc_group")

    assert [event.message_id for event in events] == ["om_visible"]
    assert events[0].text == "background question"
