"""Integration tests for feishu channel registration in main._build_channel_registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

lark_oapi = pytest.importorskip("lark_oapi")

from personal_assistant.config.local_store import ChannelConfig
from personal_assistant.main import _build_channel_registry


class TestBuildChannelRegistryFeishu:
    """Verify _build_channel_registry creates FeishuAdapter for feishu channels."""

    @patch("personal_assistant.main.FeishuAdapter")
    def test_feishu_channel_creates_adapter(self, mock_fa_cls: MagicMock) -> None:
        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        mock_fa_cls.assert_called_once()
        call_kwargs = mock_fa_cls.call_args[1]
        assert call_kwargs["app_id"] == "cli_a"
        assert call_kwargs["app_secret"] == "s_a"
        assert call_kwargs["agent_id"] == "plato"

    @patch("personal_assistant.main.FeishuAdapter")
    def test_multiple_feishu_accounts_registered(
        self, mock_fa_cls: MagicMock
    ) -> None:
        # Return distinct mock instances with unique names
        mock_plato = MagicMock()
        mock_plato.name = "feishu:plato"
        mock_luban = MagicMock()
        mock_luban.name = "feishu:luban"
        mock_fa_cls.side_effect = [mock_plato, mock_luban]

        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
            ChannelConfig(
                name="feishu:luban-bot",
                enabled=True,
                settings={
                    "name": "luban-bot",
                    "appId": "cli_b",
                    "appSecret": "s_b",
                    "agentId": "luban",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        assert mock_fa_cls.call_count == 2
        agent_ids = [c[1]["agent_id"] for c in mock_fa_cls.call_args_list]
        assert "plato" in agent_ids
        assert "luban" in agent_ids

    @patch("personal_assistant.main.FeishuAdapter")
    def test_feishu_disabled_not_registered(self, mock_fa_cls: MagicMock) -> None:
        channels = (
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=False,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        mock_fa_cls.assert_not_called()

    @patch("personal_assistant.main.FeishuAdapter")
    @patch("personal_assistant.main.WebRelayAdapter")
    def test_feishu_coexists_with_web_relay(
        self, mock_wra_cls: MagicMock, mock_fa_cls: MagicMock
    ) -> None:
        mock_adapter = MagicMock()
        mock_adapter.name = "feishu:plato"
        mock_fa_cls.return_value = mock_adapter

        channels = (
            ChannelConfig(name="web_relay", enabled=True, settings={}),
            ChannelConfig(
                name="feishu:plato-bot",
                enabled=True,
                settings={
                    "name": "plato-bot",
                    "appId": "cli_a",
                    "appSecret": "s_a",
                    "agentId": "plato",
                },
            ),
        )
        registry = _build_channel_registry(channels)
        mock_wra_cls.assert_called_once()
        mock_fa_cls.assert_called_once()
