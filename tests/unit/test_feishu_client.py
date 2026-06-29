"""Tests for FeishuClient — lark-oapi WSClient wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu_client import FeishuClient


class TestFeishuClientLifecycle:
    """Verify FeishuClient start/stop wrapping lark-oapi WSClient."""

    @patch("personal_assistant.channels.feishu_client.WSClient")
    def test_start_creates_ws_client_with_event_handler(
        self, mock_ws_cls: MagicMock
    ) -> None:
        mock_ws = MagicMock()
        mock_ws_cls.return_value = mock_ws
        client = FeishuClient(
            app_id="cli_abc",
            app_secret="secret",
        )
        on_message = MagicMock()
        client.start(on_message)
        mock_ws_cls.assert_called_once()
        call_kwargs = mock_ws_cls.call_args
        assert call_kwargs[1]["app_id"] == "cli_abc"
        assert call_kwargs[1]["app_secret"] == "secret"
        assert call_kwargs[1]["auto_reconnect"] is True
        assert call_kwargs[1]["event_handler"] is not None
        mock_ws.start.assert_called_once()

    @patch("personal_assistant.channels.feishu_client.WSClient")
    def test_stop_noop_when_not_started(self, mock_ws_cls: MagicMock) -> None:
        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        # stop before start should not raise
        client.stop()

    @patch("personal_assistant.channels.feishu_client.WSClient")
    def test_stop_after_start(self, mock_ws_cls: MagicMock) -> None:
        mock_ws = MagicMock()
        mock_ws_cls.return_value = mock_ws
        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        client.start(MagicMock())
        client.stop()
        # After stop, internal state is cleared


class TestFeishuClientEventParsing:
    """Verify FeishuClient parses P2ImMessageReceiveV1 into structured data."""

    def _make_event(
        self,
        *,
        chat_type: str = "p2p",
        content: str = '{"text":"hello"}',
        chat_id: str = "oc_abc123",
        sender_open_id: str = "ou_user1",
        message_id: str = "msg_001",
        mentions: list | None = None,
    ) -> MagicMock:
        """Build a mock P2ImMessageReceiveV1 event."""
        event = MagicMock()
        event.event.sender.sender_id.open_id = sender_open_id
        event.event.message.chat_id = chat_id
        event.event.message.chat_type = chat_type
        event.event.message.content = content
        event.event.message.message_id = message_id
        event.event.message.mentions = mentions or []
        return event

    def test_parse_p2p_message(self) -> None:
        from personal_assistant.channels.feishu_client import _parse_feishu_event

        ev = self._make_event(chat_type="p2p", content='{"text":"hi there"}')
        result = _parse_feishu_event(ev)
        assert result.text == "hi there"
        assert result.chat_type == "p2p"
        assert result.sender_open_id == "ou_user1"
        assert result.chat_id == "oc_abc123"
        assert result.message_id == "msg_001"
        assert result.is_group is False

    def test_parse_group_message(self) -> None:
        from personal_assistant.channels.feishu_client import _parse_feishu_event

        ev = self._make_event(chat_type="group")
        result = _parse_feishu_event(ev)
        assert result.is_group is True

    def test_parse_text_content_extraction(self) -> None:
        """Feishu text content is JSON: {"text": "@_user_1 actual text"}."""
        from personal_assistant.channels.feishu_client import _parse_feishu_event

        ev = self._make_event(content='{"text":"@_user_1 help me"}')
        result = _parse_feishu_event(ev)
        assert result.text == "help me"

    def test_parse_empty_content(self) -> None:
        from personal_assistant.channels.feishu_client import _parse_feishu_event

        ev = self._make_event(content="")
        result = _parse_feishu_event(ev)
        assert result.text == ""

    def test_parse_non_json_content_fallback(self) -> None:
        """Non-JSON content (e.g. image/file) should be kept as-is."""
        from personal_assistant.channels.feishu_client import _parse_feishu_event

        ev = self._make_event(content="plain text not json")
        result = _parse_feishu_event(ev)
        assert result.text == "plain text not json"

    def test_mentions_extracted(self) -> None:
        from personal_assistant.channels.feishu_client import _parse_feishu_event

        mention = MagicMock()
        mention.id.open_id = "ou_bot1"
        mention.name = "plato-bot"
        mention.key = "@_user_1"
        ev = self._make_event(
            mentions=[mention],
            content='{"text":"@_user_1 hello bot"}',
        )
        result = _parse_feishu_event(ev)
        assert len(result.mentions) == 1
        assert result.mentions[0].open_id == "ou_bot1"
        assert result.mentions[0].name == "plato-bot"
        assert result.mentions[0].key == "@_user_1"


class TestFeishuClientSendMessage:
    """Verify FeishuClient.send_message calls lark-oapi REST API."""

    @patch("personal_assistant.channels.feishu_client.WSClient")
    @patch("personal_assistant.channels.feishu_client.lark.Client")
    def test_send_message_calls_api(
        self, mock_lark_client_cls: MagicMock, mock_ws_cls: MagicMock
    ) -> None:
        mock_rest = MagicMock()
        mock_lark_client_cls.return_value = mock_rest

        # Mock the response
        mock_resp = MagicMock()
        mock_resp.success.return_value = True
        mock_resp.code = 0
        mock_rest.im.v1.message.create.return_value = mock_resp

        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        client.start(MagicMock())
        client.send_message(
            receive_id="oc_chat123",
            text="hello from bot",
            receive_id_type="chat_id",
        )
        mock_rest.im.v1.message.create.assert_called_once()
