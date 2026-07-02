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
    sender_display_name: str | None = None,
    chat_id: str = "oc_chat123",
    chat_type: str = "p2p",
    message_id: str = "msg_001",
    is_group: bool = False,
    mentions: list[FeishuMention] | None = None,
) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        sender_display_name=sender_display_name,
        chat_id=chat_id,
        chat_type=chat_type,
        message_id=message_id,
        is_group=is_group,
        mentions=mentions or [],
    )


class TestFeishuAdapterName:
    def test_name_contains_agent_id(self) -> None:
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        assert adapter.name == "feishu:plato"


class TestFeishuAdapterDM:
    """1:1 private chat scenarios."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_dm_delivers_inbound_message(self, mock_fc_cls: MagicMock) -> None:
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        event = _make_event(
            text="hi there", sender_open_id="ou_user1", chat_id="oc_dm1"
        )
        adapter._handle_message(event)

        on_inbound.assert_called_once()
        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.text == "hi there"
        assert msg.agent_id == "plato"
        assert msg.external_user_id == "ou_user1"
        assert msg.is_group is False
        assert msg.channel_name == "feishu:plato"
        # DM external_chat_id uses sender_open_id per design
        assert msg.external_chat_id == "feishu:cli_a:dm:ou_user1"
        assert msg.metadata["external_source"] == "feishu"
        assert msg.metadata["external_chat_id"] == "feishu:cli_a:dm:ou_user1"
        assert msg.metadata["trigger_source"] == "feishu"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_dm_always_responds_no_mention_needed(self, mock_fc_cls: MagicMock) -> None:
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        # No mentions in DM — should still deliver
        event = _make_event(text="no mention here", chat_type="p2p")
        adapter._handle_message(event)
        on_inbound.assert_called_once()

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_dm_adds_ack_reaction(self, mock_fc_cls: MagicMock) -> None:
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter.start(MagicMock())

        event = _make_event(message_id="om_msg_001")
        adapter._handle_message(event)

        mock_fc.add_reaction.assert_called_once_with(
            message_id="om_msg_001",
            emoji_type="THINKING",
        )

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_ack_reaction_failure_still_delivers_dm(
        self, mock_fc_cls: MagicMock
    ) -> None:
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_fc = MagicMock()
        mock_fc.add_reaction.side_effect = FeishuAPIError("reaction failed", code=99999)
        mock_fc_cls.return_value = mock_fc
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        event = _make_event(message_id="om_msg_001")
        adapter._handle_message(event)

        mock_fc.add_reaction.assert_called_once()
        on_inbound.assert_called_once()


class TestFeishuAdapterGroupMention:
    """Group chat @Bot trigger scenarios."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_at_bot_delivers_inbound(self, mock_fc_cls: MagicMock) -> None:
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc
        store = MagicMock(spec=GroupContextStore)
        store.drain.return_value = []
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
        event = _make_event(
            text="@_user_1 help me",
            chat_type="group",
            is_group=True,
            chat_id="oc_grp1",
            mentions=[mention],
        )
        adapter._handle_message(event)

        on_inbound.assert_called_once()
        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.is_group is True
        assert msg.agent_id == "plato"
        assert "oc_grp1" in msg.external_chat_id
        mock_fc.add_reaction.assert_called_once_with(
            message_id="msg_001",
            emoji_type="THINKING",
        )

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_no_mention_delivers_sync_only_inbound(
        self, mock_fc_cls: MagicMock
    ) -> None:
        store = MagicMock(spec=GroupContextStore)
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            owner_open_id="ou_owner",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        event = _make_event(
            text="just chatting",
            chat_type="group",
            is_group=True,
            chat_id="oc_grp1",
            sender_open_id="ou_user1",
            sender_display_name="Alice",
        )
        adapter._handle_message(event)

        on_inbound.assert_called_once()
        store.append.assert_not_called()
        mock_fc_cls.return_value.add_reaction.assert_not_called()
        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.is_group is True
        assert msg.external_chat_id == "feishu:cli_a:group:oc_grp1"
        assert msg.metadata["sync_only"] is True
        assert msg.metadata["external_source"] == "feishu"
        assert msg.metadata["external_chat_id"] == "feishu:cli_a:group:oc_grp1"
        assert msg.metadata["trigger_source"] == "feishu"
        assert msg.metadata["sender_display_name"] == "Alice"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_inbound_metadata_includes_chat_name(
        self, mock_fc_cls: MagicMock
    ) -> None:
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

        mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
        event = _make_event(
            text="@_user_1 help",
            chat_type="group",
            is_group=True,
            chat_id="oc_grp1",
            mentions=[mention],
        )
        adapter._handle_message(event)

        msg: InboundMessage = on_inbound.call_args[0][0]
        mock_fc.get_chat_name.assert_called_once_with("oc_grp1")
        assert msg.metadata["chat_name"] == "产品群"
        assert msg.metadata["conversation_title"] == "plato · 产品群 · feishu"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_owner_open_id_maps_sender_display_name_to_you(
        self, mock_fc_cls: MagicMock
    ) -> None:
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            owner_open_id="ou_owner",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        event = _make_event(sender_open_id="ou_owner", sender_display_name="CZJ")
        adapter._handle_message(event)

        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.metadata["sender_display_name"] == "你"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_at_bot_delivers_mention_for_pipeline_buffer_drain(
        self, mock_fc_cls: MagicMock
    ) -> None:
        store = MagicMock(spec=GroupContextStore)
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        mention = FeishuMention(open_id="ou_bot1", name="plato", key="@_user_1")
        event = _make_event(
            text="@_user_1 summarize",
            chat_type="group",
            is_group=True,
            chat_id="oc_grp1",
            mentions=[mention],
        )
        adapter._handle_message(event)

        on_inbound.assert_called_once()
        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.text == "@_user_1 summarize"
        assert msg.metadata["mentioned_agent_ids"] == ["plato"]
        assert "sync_only" not in msg.metadata
        store.drain.assert_not_called()

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_group_at_everyone_does_not_trigger(self, mock_fc_cls: MagicMock) -> None:
        store = MagicMock(spec=GroupContextStore)
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            bot_open_id="ou_bot1",
            group_context_store=store,
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        # @所有人 — mention with open_id "all" (feishu convention) or no bot mention
        mention_all = FeishuMention(open_id="all", name="所有人", key="@_user_1")
        event = _make_event(
            text="@_user_1 hey everyone",
            chat_type="group",
            is_group=True,
            mentions=[mention_all],
        )
        adapter._handle_message(event)

        on_inbound.assert_called_once()
        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.metadata["sync_only"] is True
        store.append.assert_not_called()


class TestFeishuAdapterMultiBot:
    """Multiple bot routing — different agent_id per adapter."""

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_different_agents_get_different_channel_names(
        self, mock_fc_cls: MagicMock
    ) -> None:
        adapter_plato = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        adapter_luban = FeishuAdapter(
            app_id="cli_b",
            app_secret="s",
            name="feishu:luban",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        assert adapter_plato.name == "feishu:plato"
        assert adapter_luban.name == "feishu:luban"

    @patch("personal_assistant.channels.feishu_adapter.FeishuClient")
    def test_message_routed_to_correct_agent(self, mock_fc_cls: MagicMock) -> None:
        adapter = FeishuAdapter(
            app_id="cli_a",
            app_secret="s",
            name="feishu:plato",
            group_context_store=MagicMock(spec=GroupContextStore),
        )
        on_inbound = MagicMock()
        adapter.start(on_inbound)

        event = _make_event(text="hello")
        adapter._handle_message(event)

        msg: InboundMessage = on_inbound.call_args[0][0]
        assert msg.agent_id == "plato"
