"""Tests for feishu channel config parsing in local_store."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    ChannelConfig,
    _parse_channels,
)


class TestParseFeishuAccounts:
    """Verify channels.feishu.accounts parsing into ChannelConfig entries."""

    def test_single_feishu_account(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_abc123",
                        "appSecret": "secret123",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        ch = channels[0]
        assert ch.name == "feishu:plato-bot"
        assert ch.enabled is True
        assert ch.settings["appId"] == "cli_abc123"
        assert ch.settings["appSecret"] == "secret123"
        assert ch.settings["agentId"] == "plato"

    def test_multiple_feishu_accounts(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "s_a",
                        "agentId": "plato",
                    },
                    {
                        "name": "luban-bot",
                        "appId": "cli_b",
                        "appSecret": "s_b",
                        "agentId": "luban",
                    },
                    {
                        "name": "hume-bot",
                        "appId": "cli_c",
                        "appSecret": "s_c",
                        "agentId": "hume",
                    },
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 3
        names = [ch.name for ch in channels]
        assert names == ["feishu:plato-bot", "feishu:luban-bot", "feishu:hume-bot"]
        agent_ids = [ch.settings["agentId"] for ch in channels]
        assert agent_ids == ["plato", "luban", "hume"]

    def test_disabled_feishu_account_excluded(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "s_a",
                        "agentId": "plato",
                    },
                    {
                        "name": "luban-bot",
                        "appId": "cli_b",
                        "appSecret": "s_b",
                        "agentId": "luban",
                        "enabled": False,
                    },
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        assert channels[0].name == "feishu:plato-bot"

    def test_missing_app_id_raises(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appSecret": "secret",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        with pytest.raises(ValueError, match="appId"):
            _parse_channels(payload)

    def test_missing_app_secret_raises(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        with pytest.raises(ValueError, match="appSecret"):
            _parse_channels(payload)

    def test_missing_agent_id_raises(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "secret",
                    }
                ],
            }
        ]
        with pytest.raises(ValueError, match="agentId"):
            _parse_channels(payload)

    def test_missing_name_raises(self) -> None:
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "appId": "cli_a",
                        "appSecret": "secret",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        with pytest.raises(ValueError, match="name"):
            _parse_channels(payload)

    def test_empty_accounts_list(self) -> None:
        payload = [{"name": "feishu", "accounts": []}]
        channels = _parse_channels(payload)
        assert channels == ()

    def test_feishu_combined_with_other_channels(self) -> None:
        """feishu accounts + regular channel entries coexist."""
        payload = [
            {"name": "web_relay"},
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_a",
                        "appSecret": "s_a",
                        "agentId": "plato",
                    }
                ],
            },
        ]
        channels = _parse_channels(payload)
        names = [ch.name for ch in channels]
        assert "web_relay" in names
        assert "feishu:plato-bot" in names
        assert len(channels) == 2

    def test_none_payload_returns_empty(self) -> None:
        assert _parse_channels(None) == ()

    def test_feishu_account_settings_preserved(self) -> None:
        """Settings dict carries all account fields for adapter use."""
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_x",
                        "appSecret": "sec",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        channels = _parse_channels(payload)
        settings = channels[0].settings
        assert settings["name"] == "plato-bot"
        assert settings["appId"] == "cli_x"
        assert settings["appSecret"] == "sec"
        assert settings["agentId"] == "plato"

    def test_feishu_account_with_bot_open_id_preserved(self) -> None:
        """botOpenId in account settings is preserved for adapter mention detection."""
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_abc",
                        "appSecret": "sec",
                        "agentId": "plato",
                        "botOpenId": "ou_bot_123",
                    }
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        settings = channels[0].settings
        assert settings["botOpenId"] == "ou_bot_123"

    def test_feishu_account_without_bot_open_id_omits_key(self) -> None:
        """When botOpenId is absent, settings does not contain the key."""
        payload = [
            {
                "name": "feishu",
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_abc",
                        "appSecret": "sec",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert "botOpenId" not in channels[0].settings

    def test_feishu_top_level_enabled_false_skips_accounts(self) -> None:
        """feishu channel with enabled: false should not parse any accounts."""
        payload = [
            {
                "name": "feishu",
                "enabled": False,
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_abc",
                        "appSecret": "sec",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert channels == ()

    def test_feishu_top_level_enabled_true_parses_accounts(self) -> None:
        """feishu channel with enabled: true (explicit) should parse accounts normally."""
        payload = [
            {
                "name": "feishu",
                "enabled": True,
                "accounts": [
                    {
                        "name": "plato-bot",
                        "appId": "cli_abc",
                        "appSecret": "sec",
                        "agentId": "plato",
                    }
                ],
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        assert channels[0].name == "feishu:plato-bot"
