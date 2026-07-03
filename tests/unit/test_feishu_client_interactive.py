"""Tests for FeishuClient interactive card support."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import (
    FeishuCardActionEvent,
    FeishuClient,
)


class TestFeishuClientInteractive:
    """Verify Feishu interactive card sending and callbacks."""

    @patch("personal_assistant.channels.feishu.client.EventDispatcherHandler")
    @patch("personal_assistant.channels.feishu.client.WSClient")
    def test_start_registers_card_action_handler(
        self, mock_ws_cls: MagicMock, mock_dispatcher: MagicMock
    ) -> None:
        mock_builder = MagicMock()
        mock_builder.register_p2_im_message_receive_v1.return_value = mock_builder
        mock_builder.register_p2_card_action_trigger.return_value = mock_builder
        mock_builder.build.return_value = MagicMock()
        mock_dispatcher.builder.return_value = mock_builder

        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        client.start(MagicMock(), on_card_action=MagicMock())

        mock_builder.register_p2_card_action_trigger.assert_called_once_with(
            client._handle_card_action_event
        )

    def test_send_interactive_message_calls_api_and_returns_message_id(self) -> None:
        mock_rest = MagicMock()
        mock_resp = MagicMock()
        mock_resp.success.return_value = True
        mock_resp.code = 0
        mock_resp.data.message_id = "om_card_001"
        mock_rest.im.v1.message.create.return_value = mock_resp

        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        client._rest_client = mock_rest

        message_id = client.send_interactive_message(
            receive_id="oc_chat123",
            receive_id_type="chat_id",
            card={"config": {"wide_screen_mode": True}},
        )

        assert message_id == "om_card_001"
        request = mock_rest.im.v1.message.create.call_args[0][0]
        assert request.receive_id_type == "chat_id"
        assert request.request_body.receive_id == "oc_chat123"
        assert request.request_body.msg_type == "interactive"
        assert json.loads(request.request_body.content)["config"]["wide_screen_mode"] is True

    def test_update_interactive_message_calls_api(self) -> None:
        mock_rest = MagicMock()
        mock_resp = MagicMock()
        mock_resp.success.return_value = True
        mock_resp.code = 0
        mock_rest.im.v1.message.update.return_value = mock_resp

        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        client._rest_client = mock_rest

        client.update_interactive_message(
            message_id="om_card_001",
            card={"header": {"template": "green"}},
        )

        request = mock_rest.im.v1.message.update.call_args[0][0]
        assert request.message_id == "om_card_001"
        assert request.request_body.msg_type == "interactive"
        assert json.loads(request.request_body.content)["header"]["template"] == "green"

    def test_card_action_event_parses_and_returns_card_response(self) -> None:
        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        on_card_action = MagicMock(
            return_value={"config": {"wide_screen_mode": True}}
        )
        client._on_card_action = on_card_action
        raw_event = MagicMock()
        raw_event.event.action.value = {"approval_id": "appr-1", "decision": "allow"}
        raw_event.event.operator.open_id = "ou_owner"
        raw_event.event.operator.user_id = "u_owner"
        raw_event.event.context.open_chat_id = "oc_group"

        response = client._handle_card_action_event(raw_event)

        parsed: FeishuCardActionEvent = on_card_action.call_args[0][0]
        assert parsed.action_value["approval_id"] == "appr-1"
        assert parsed.operator_open_id == "ou_owner"
        assert parsed.operator_user_id == "u_owner"
        assert parsed.open_chat_id == "oc_group"
        assert response.card.data["config"]["wide_screen_mode"] is True
