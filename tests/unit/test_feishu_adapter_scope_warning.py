"""Tests for Feishu adapter startup scope diagnostics."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu_adapter import FeishuAdapter
from personal_assistant.gateway.group_context_store import GroupContextStore


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_start_warns_when_group_message_scope_missing(
    mock_fc_cls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    mock_fc = MagicMock()
    mock_fc.has_scope.return_value = False
    mock_fc_cls.return_value = mock_fc
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        group_context_store=MagicMock(spec=GroupContextStore),
    )

    with caplog.at_level(
        logging.WARNING, logger="personal_assistant.channels.feishu_adapter"
    ):
        adapter.start(MagicMock())

    assert "im:message.group_msg" in caplog.text
    assert "ordinary group messages" in caplog.text
    assert "receiveAllGroupMessages" not in caplog.text


@patch("personal_assistant.channels.feishu_adapter.FeishuClient")
def test_start_does_not_warn_when_group_message_scope_present(
    mock_fc_cls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    mock_fc = MagicMock()
    mock_fc.has_scope.return_value = True
    mock_fc_cls.return_value = mock_fc
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="s",
        name="feishu:plato",
        group_context_store=MagicMock(spec=GroupContextStore),
    )

    with caplog.at_level(
        logging.WARNING, logger="personal_assistant.channels.feishu_adapter"
    ):
        adapter.start(MagicMock())

    assert "im:message.group_msg" not in caplog.text
