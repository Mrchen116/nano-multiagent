"""Tests for FeishuClient chat metadata lookups."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import FeishuAPIError, FeishuClient


def test_get_chat_name_returns_group_name() -> None:
    mock_rest = MagicMock()
    response = MagicMock()
    response.success.return_value = True
    response.code = 0
    response.data.name = "产品群"
    mock_rest.im.v1.chat.get.return_value = response
    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = mock_rest

    assert client.get_chat_name("oc_chat123") == "产品群"
    request = mock_rest.im.v1.chat.get.call_args[0][0]
    assert request.chat_id == "oc_chat123"


def test_get_chat_name_failure_raises_feishu_api_error() -> None:
    mock_rest = MagicMock()
    response = MagicMock()
    response.success.return_value = False
    response.code = 99999
    response.msg = "bad chat"
    mock_rest.im.v1.chat.get.return_value = response
    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = mock_rest

    with pytest.raises(FeishuAPIError):
        client.get_chat_name("oc_chat123")
