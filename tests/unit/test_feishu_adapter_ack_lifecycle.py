"""FeishuAdapter ack reaction lifecycle tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import OutboundMessage
from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.gateway.group_context_store import GroupContextStore


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_control_reply_removes_ack_reaction(mock_fc_cls: MagicMock) -> None:
    mock_fc = MagicMock()
    mock_fc.add_reaction.return_value = "reaction_001"
    mock_fc_cls.return_value = mock_fc
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(MagicMock())

    adapter.ack_message("om_msg_001")
    adapter.send(
        OutboundMessage(
            channel_name="feishu:plato",
            text="已停止当前操作。",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={
                "reply_phase": "control",
                "feishu_message_id": "om_msg_001",
            },
        )
    )

    mock_fc.send_message.assert_called_once_with(
        receive_id="ou_user1",
        text="已停止当前操作。",
        receive_id_type="open_id",
    )
    mock_fc.delete_reaction.assert_called_once_with(
        message_id="om_msg_001",
        reaction_id="reaction_001",
    )
