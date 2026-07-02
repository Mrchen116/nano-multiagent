"""Tests for FeishuAdapter — ChannelAdapter implementation for feishu."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.channels.feishu_adapter import FeishuAdapter
from personal_assistant.channels.feishu_client import FeishuMessageEvent, FeishuMention
from personal_assistant.gateway.group_context_store import GroupContextStore


def _make_event(
    *,
    text: str = "hello",
    sender_open_id: str = "ou_user1",
    chat_id: str = "oc_chat123",
    chat_type: str = "p2p",
    message_id: str = "msg_001",
    is_group: bool = False,
    mentions: list[FeishuMention] | None = None,
) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        chat_id=chat_id,
        chat_type=chat_type,
        message_id=message_id,
        is_group=is_group,
        mentions=mentions or [],
    )


class TestFeishuAdapterSend:
    """Outbound message sending via FeishuClient."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_calls_feishu_client(self, mock_fc_cls: MagicMock) -> None:
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())

        outbound = OutboundMessage(
            channel_name="feishu:plato",
            text="reply from bot",
            target_chat_id="oc_chat123",
            metadata={"feishu_message_id": "msg_001"},
        )
        adapter.send(outbound)

        mock_fc.send_message.assert_called_once()
        call_kwargs = mock_fc.send_message.call_args[1]
        assert call_kwargs["receive_id"] == "oc_chat123"
        assert call_kwargs["text"] == "reply from bot"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_removes_ack_reaction_only_after_final_reply(
        self, mock_fc_cls: MagicMock
    ) -> None:
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
        adapter._handle_message(_make_event(message_id="om_msg_001"))

        intermediate = OutboundMessage(
            channel_name="feishu:plato",
            text="I will check.",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={
                "feishu_message_id": "om_msg_001",
                "reply_phase": "intermediate",
            },
        )
        adapter.send(intermediate)

        mock_fc.send_message.assert_called_once()
        mock_fc.delete_reaction.assert_not_called()

        final = OutboundMessage(
            channel_name="feishu:plato",
            text="reply from bot",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={"feishu_message_id": "om_msg_001", "reply_phase": "final"},
        )
        adapter.send(final)

        mock_fc.delete_reaction.assert_called_once_with(
            message_id="om_msg_001",
            reaction_id="reaction_001",
        )

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_failure_keeps_ack_reaction(self, mock_fc_cls: MagicMock) -> None:
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_fc = MagicMock()
        mock_fc.add_reaction.return_value = "reaction_001"
        mock_fc.send_message.side_effect = FeishuAPIError("send failed", code=500)
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())
        adapter._handle_message(_make_event(message_id="om_msg_001"))

        outbound = OutboundMessage(
            channel_name="feishu:plato",
            text="reply from bot",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={"feishu_message_id": "om_msg_001"},
        )
        with pytest.raises(FeishuAPIError):
            adapter.send(outbound)

        mock_fc.delete_reaction.assert_not_called()

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_dm_uses_open_id(self, mock_fc_cls: MagicMock) -> None:
        """DM replies must use receive_id_type='open_id' (user open_id)."""
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())

        outbound = OutboundMessage(
            channel_name="feishu:plato",
            text="dm reply",
            target_chat_id="feishu:cli_a:dm:ou_user1",
            metadata={},
        )
        adapter.send(outbound)

        call_kwargs = mock_fc.send_message.call_args[1]
        assert call_kwargs["receive_id"] == "ou_user1"
        assert call_kwargs["receive_id_type"] == "open_id"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_group_uses_chat_id(self, mock_fc_cls: MagicMock) -> None:
        """Group replies must use receive_id_type='chat_id'."""
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())

        outbound = OutboundMessage(
            channel_name="feishu:plato",
            text="group reply",
            target_chat_id="feishu:cli_a:group:oc_grp1",
            metadata={},
        )
        adapter.send(outbound)

        call_kwargs = mock_fc.send_message.call_args[1]
        assert call_kwargs["receive_id"] == "oc_grp1"
        assert call_kwargs["receive_id_type"] == "chat_id"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_stop_stops_client(self, mock_fc_cls: MagicMock) -> None:
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())
        adapter.stop()
        mock_fc.stop.assert_called_once()


class TestFeishuAdapterErrorNotification:
    """Verify adapter.send catches feishu errors and logs structured context."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_auth_error_logs_and_reraises(self, mock_fc_cls: MagicMock) -> None:
        """FeishuAuthError should be logged with structured context and re-raised."""
        from personal_assistant.channels.feishu_client import FeishuAuthError

        mock_fc = MagicMock()
        mock_fc.send_message.side_effect = FeishuAuthError("auth expired", code=401)
        mock_fc_cls.return_value = mock_fc

        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())

        outbound = OutboundMessage(
            channel_name="feishu:plato",
            text="reply",
            target_chat_id="feishu:cli_a:group:oc_chat123",
            metadata={},
        )
        with pytest.raises(FeishuAuthError):
            adapter.send(outbound)

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_send_api_error_logs_and_reraises(self, mock_fc_cls: MagicMock) -> None:
        """FeishuAPIError should be logged with structured context and re-raised."""
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_fc = MagicMock()
        mock_fc.send_message.side_effect = FeishuAPIError("server error", code=500)
        mock_fc_cls.return_value = mock_fc

        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())

        outbound = OutboundMessage(
            channel_name="feishu:plato",
            text="reply",
            target_chat_id="feishu:cli_a:group:oc_chat123",
            metadata={},
        )
        with pytest.raises(FeishuAPIError):
            adapter.send(outbound)
