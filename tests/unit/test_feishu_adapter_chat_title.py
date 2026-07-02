"""Tests for FeishuAdapter group shadow title metadata."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.feishu_adapter import FeishuAdapter
from personal_assistant.channels.feishu_client import (
    FeishuAPIError,
    FeishuMention,
    FeishuMessageEvent,
)
from personal_assistant.gateway.group_context_store import GroupContextStore


def _group_event() -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text="@_user_1 help",
        sender_open_id="ou_user1",
        chat_id="oc_grp1",
        chat_type="group",
        message_id="msg_001",
        is_group=True,
        mentions=[FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")],
    )


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_inbound_metadata_includes_chat_name(mock_fc_cls: MagicMock) -> None:
    mock_fc = MagicMock()
    mock_fc.get_chat_name.return_value = "产品群"
    mock_fc_cls.return_value = mock_fc
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    adapter._handle_message(_group_event())

    msg: InboundMessage = on_inbound.call_args[0][0]
    mock_fc.get_chat_name.assert_called_once_with("oc_grp1")
    assert msg.metadata["chat_name"] == "产品群"
    assert msg.metadata["conversation_title"] == "plato · 产品群 · feishu"


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_group_chat_name_lookup_failure_still_delivers_inbound(
    mock_fc_cls: MagicMock,
) -> None:
    mock_fc = MagicMock()
    mock_fc.get_chat_name.side_effect = FeishuAPIError("chat lookup failed", code=1)
    mock_fc_cls.return_value = mock_fc
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        bot_open_id="ou_bot1",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    adapter._handle_message(_group_event())

    msg: InboundMessage = on_inbound.call_args[0][0]
    assert msg.external_chat_id == "feishu:cli_a:group:oc_grp1"
    assert "chat_name" not in msg.metadata
    assert "conversation_title" not in msg.metadata
