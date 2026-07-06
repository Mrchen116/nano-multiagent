"""Tests for Feishu app scope inspection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.client import FeishuClient


def _mock_scope_response(*, success: bool, scopes: list[object] | None = None):
    resp = MagicMock()
    resp.success.return_value = success
    resp.code = 0 if success else 403
    resp.msg = "" if success else "forbidden"
    resp.data = {"scopes": scopes or []}
    return resp


def test_has_scope_returns_true_when_scope_present() -> None:
    mock_rest = MagicMock()
    mock_rest.application.v6.scope.list.return_value = _mock_scope_response(
        success=True,
        scopes=[{"scope_name": "im:message.group_msg"}],
    )
    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = mock_rest

    assert client.has_scope("im:message.group_msg") is True


def test_has_scope_returns_false_when_scope_absent() -> None:
    mock_rest = MagicMock()
    mock_rest.application.v6.scope.list.return_value = _mock_scope_response(
        success=True,
        scopes=[{"scope_name": "im:message"}],
    )
    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = mock_rest

    assert client.has_scope("im:message.group_msg") is False


def test_has_scope_returns_none_when_scope_list_fails() -> None:
    mock_rest = MagicMock()
    mock_rest.application.v6.scope.list.return_value = _mock_scope_response(
        success=False
    )
    client = FeishuClient(app_id="cli_abc", app_secret="secret")
    client._rest_client = mock_rest

    assert client.has_scope("im:message.group_msg") is None
