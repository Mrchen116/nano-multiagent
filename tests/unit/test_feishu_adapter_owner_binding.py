"""Security-relevant owner binding behavior for Feishu inbound messages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import FeishuMessageEvent
from personal_assistant.gateway.group_context_store import GroupContextStore


def _event(*, sender: str, is_group: bool = False) -> FeishuMessageEvent:
    return FeishuMessageEvent(
        text="hello",
        sender_open_id=sender,
        sender_display_name="CZJ",
        chat_id="oc_group" if is_group else "oc_direct",
        chat_type="group" if is_group else "p2p",
        message_id="message-1",
        is_group=is_group,
        mentions=[],
        raw_text="hello",
        mention_only=False,
    )


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_configured_owner_is_displayed_as_you_without_rebinding(
    mock_client_class: MagicMock,
) -> None:
    binder = MagicMock()
    on_inbound = MagicMock()
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        owner_open_id="ou_owner",
        owner_open_id_binder=binder,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(on_inbound)

    adapter._handle_message(_event(sender="ou_owner"))

    binder.assert_not_called()
    assert on_inbound.call_args.args[0].metadata["sender_display_name"] == "你"


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_first_real_inbound_sender_binds_missing_owner(
    mock_client_class: MagicMock,
) -> None:
    binder = MagicMock(return_value="ou_first")
    on_inbound = MagicMock()
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        owner_open_id_binder=binder,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(on_inbound)

    adapter._handle_message(_event(sender="ou_first"))

    binder.assert_called_once_with("feishu:plato", "ou_first")
    assert on_inbound.call_args.args[0].metadata["sender_display_name"] == "你"


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_history_catchup_never_claims_missing_owner(
    mock_client_class: MagicMock,
) -> None:
    binder = MagicMock(return_value="ou_history")
    on_inbound = MagicMock()
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        owner_open_id_binder=binder,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(on_inbound)

    adapter._deliver_group(
        _event(sender="ou_history", is_group=True),
        sync_only=True,
        source="history_catchup",
    )

    binder.assert_not_called()
    assert on_inbound.call_args.args[0].metadata["sender_display_name"] == "CZJ"
