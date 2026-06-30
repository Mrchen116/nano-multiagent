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

        mention = MagicMock()
        mention.id.open_id = "ou_bot1"
        mention.name = "plato-bot"
        mention.key = "@_user_1"
        ev = self._make_event(
            content='{"text":"@_user_1 help me"}',
            mentions=[mention],
        )
        result = _parse_feishu_event(ev)
        # Placeholder is stripped and mention removed from text
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
    @patch("personal_assistant.channels.feishu_client.lark")
    def test_send_message_calls_api(
        self, mock_lark: MagicMock, mock_ws_cls: MagicMock
    ) -> None:
        mock_rest = MagicMock()
        mock_builder = MagicMock()
        mock_builder.app_id.return_value = mock_builder
        mock_builder.app_secret.return_value = mock_builder
        mock_builder.domain.return_value = mock_builder
        mock_builder.build.return_value = mock_rest
        mock_lark.Client.builder.return_value = mock_builder

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


class TestFeishuClientErrorClassification:
    """Verify send_message classifies feishu API errors correctly."""

    def _make_started_client(
        self, mock_rest: MagicMock
    ) -> FeishuClient:
        """Create a FeishuClient with mocked REST client (bypasses WSClient)."""
        client = FeishuClient(app_id="cli_abc", app_secret="secret")
        # Inject mocked REST client directly — no WSClient needed for send tests
        client._rest_client = mock_rest
        return client

    def _mock_response(
        self, *, success: bool, code: int, msg: str = ""
    ) -> MagicMock:
        """Build a mock lark-oapi API response."""
        resp = MagicMock()
        resp.success.return_value = success
        resp.code = code
        resp.msg = msg
        return resp

    @patch("time.sleep")
    def test_rate_limit_retries_with_exponential_backoff(
        self, mock_sleep: MagicMock
    ) -> None:
        """429 (rate limit) should retry up to 3 times with exponential backoff."""
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_rest = MagicMock()
        # First 2 calls return 429, 3rd succeeds
        rate_limit_resp = self._mock_response(success=False, code=429, msg="rate limit")
        ok_resp = self._mock_response(success=True, code=0)
        mock_rest.im.v1.message.create.side_effect = [
            rate_limit_resp, rate_limit_resp, ok_resp
        ]

        client = self._make_started_client(mock_rest)
        # Should succeed after retries — no exception
        client.send_message(receive_id="oc_chat123", text="hello")

        assert mock_rest.im.v1.message.create.call_count == 3
        assert mock_sleep.call_count == 2  # 2 sleeps between 3 attempts

    @patch("time.sleep")
    def test_rate_limit_exhausted_raises_feishu_api_error(
        self, mock_sleep: MagicMock
    ) -> None:
        """429 after max retries should raise FeishuAPIError."""
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_rest = MagicMock()
        rate_limit_resp = self._mock_response(success=False, code=429, msg="rate limit")
        mock_rest.im.v1.message.create.return_value = rate_limit_resp

        client = self._make_started_client(mock_rest)
        with pytest.raises(FeishuAPIError) as exc_info:
            client.send_message(receive_id="oc_chat123", text="hello")

        assert mock_rest.im.v1.message.create.call_count == 3  # max retries
        assert "429" in str(exc_info.value)

    def test_auth_error_raises_feishu_auth_error(self) -> None:
        """401/403 should raise FeishuAuthError (no retry)."""
        from personal_assistant.channels.feishu_client import FeishuAuthError

        for code in (401, 403):
            mock_rest = MagicMock()
            auth_resp = self._mock_response(success=False, code=code, msg="auth error")
            mock_rest.im.v1.message.create.return_value = auth_resp

            client = self._make_started_client(mock_rest)
            with pytest.raises(FeishuAuthError) as exc_info:
                client.send_message(receive_id="oc_chat123", text="hello")

            assert mock_rest.im.v1.message.create.call_count == 1  # no retry
            assert str(code) in str(exc_info.value)

    @patch("time.sleep")
    def test_server_error_retries_once(
        self, mock_sleep: MagicMock
    ) -> None:
        """5xx should retry exactly once, then raise FeishuAPIError if still failing."""
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_rest = MagicMock()
        server_resp = self._mock_response(success=False, code=500, msg="internal error")
        mock_rest.im.v1.message.create.return_value = server_resp

        client = self._make_started_client(mock_rest)
        with pytest.raises(FeishuAPIError):
            client.send_message(receive_id="oc_chat123", text="hello")

        assert mock_rest.im.v1.message.create.call_count == 2  # 1 attempt + 1 retry

    @patch("time.sleep")
    def test_rate_limit_then_server_error_retries_independently(
        self, mock_sleep: MagicMock
    ) -> None:
        """429 retries and 5xx retries must use independent counters.

        A 429 that exhausts its retry budget must NOT consume the 5xx retry budget.
        """
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_rest = MagicMock()
        # 429 → 429 → 429 (exhausted) → 500 (should still get 1 retry)
        rate_limit_resp = self._mock_response(success=False, code=429, msg="rate limit")
        server_err_resp = self._mock_response(success=False, code=500, msg="server error")
        ok_resp = self._mock_response(success=True, code=0)
        mock_rest.im.v1.message.create.side_effect = [
            rate_limit_resp, rate_limit_resp, rate_limit_resp,
            server_err_resp, ok_resp,
        ]

        client = self._make_started_client(mock_rest)
        # Should succeed after 429 exhausts + 5xx retries once
        client.send_message(receive_id="oc_chat123", text="hello")

        # 3 rate-limit attempts + 2 server-error attempts (1 fail + 1 retry succeed)
        assert mock_rest.im.v1.message.create.call_count == 5
        assert mock_sleep.call_count == 4  # 2 sleeps for 429 + 1 for 5xx

    @patch("time.sleep")
    def test_server_error_retry_succeeds(
        self, mock_sleep: MagicMock
    ) -> None:
        """5xx first call fails, retry succeeds → no exception."""
        mock_rest = MagicMock()
        server_resp = self._mock_response(success=False, code=502, msg="bad gateway")
        ok_resp = self._mock_response(success=True, code=0)
        mock_rest.im.v1.message.create.side_effect = [server_resp, ok_resp]

        client = self._make_started_client(mock_rest)
        client.send_message(receive_id="oc_chat123", text="hello")

        assert mock_rest.im.v1.message.create.call_count == 2

    def test_unknown_error_raises_feishu_api_error(self) -> None:
        """Non-retryable unknown errors should raise FeishuAPIError immediately."""
        from personal_assistant.channels.feishu_client import FeishuAPIError

        mock_rest = MagicMock()
        err_resp = self._mock_response(success=False, code=99999, msg="unknown")
        mock_rest.im.v1.message.create.return_value = err_resp

        client = self._make_started_client(mock_rest)
        with pytest.raises(FeishuAPIError) as exc_info:
            client.send_message(receive_id="oc_chat123", text="hello")

        assert mock_rest.im.v1.message.create.call_count == 1  # no retry
        assert "99999" in str(exc_info.value)

    def test_success_returns_without_error(self) -> None:
        """200/success response should not raise."""
        mock_rest = MagicMock()
        ok_resp = self._mock_response(success=True, code=0)
        mock_rest.im.v1.message.create.return_value = ok_resp

        client = self._make_started_client(mock_rest)
        client.send_message(receive_id="oc_chat123", text="hello")

        mock_rest.im.v1.message.create.assert_called_once()
