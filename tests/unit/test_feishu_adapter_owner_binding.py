"""Tests for FeishuAdapter owner identity binding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.base import InboundMessage
from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import FeishuMessageEvent
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
) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text=text,
        sender_open_id=sender_open_id,
        sender_display_name=sender_display_name,
        chat_id=chat_id,
        chat_type=chat_type,
        message_id=message_id,
        is_group=is_group,
        mentions=[],
        raw_text=text,
        mention_only=False,
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_owner_open_id_maps_sender_display_name_to_you(mock_fc_cls: MagicMock) -> None:
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


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_missing_owner_open_id_binds_first_real_inbound_sender(
    mock_fc_cls: MagicMock,
) -> None:
    bound: list[tuple[str, str]] = []

    def _bind(channel_name: str, sender_open_id: str) -> str:
        bound.append((channel_name, sender_open_id))
        return sender_open_id

    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        owner_open_id_binder=_bind,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    event = _make_event(sender_open_id="ou_first", sender_display_name="CZJ")
    adapter._handle_message(event)

    msg: InboundMessage = on_inbound.call_args[0][0]
    assert bound == [("feishu:plato", "ou_first")]
    assert msg.metadata["sender_display_name"] == "你"


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_existing_owner_open_id_does_not_rebind(mock_fc_cls: MagicMock) -> None:
    binder = MagicMock(return_value="ou_other")
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        owner_open_id="ou_owner",
        owner_open_id_binder=binder,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    event = _make_event(sender_open_id="ou_owner", sender_display_name="CZJ")
    adapter._handle_message(event)

    binder.assert_not_called()
    msg: InboundMessage = on_inbound.call_args[0][0]
    assert msg.metadata["sender_display_name"] == "你"


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_history_catchup_does_not_bind_missing_owner(mock_fc_cls: MagicMock) -> None:
    binder = MagicMock(return_value="ou_history")
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        owner_open_id_binder=binder,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    on_inbound = MagicMock()
    adapter.start(on_inbound)

    event = _make_event(
        sender_open_id="ou_history",
        sender_display_name="History User",
        chat_id="oc_group",
        chat_type="group",
        is_group=True,
    )
    adapter._deliver_group(event, sync_only=True, source="history_catchup")

    binder.assert_not_called()
    msg: InboundMessage = on_inbound.call_args[0][0]
    assert msg.metadata["sender_display_name"] == "History User"
