"""Tests for feishu channel config parsing in local_store."""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    ChannelConfig,
    _parse_channels,
)


class TestParseFeishuChannels:
    """Verify channels named "feishu:<agent_id>" parse into ChannelConfig entries."""

    def test_single_feishu_channel(self) -> None:
        payload = [
            {
                "name": "feishu:plato",
                "settings": {
                    "appId": "cli_abc123",
                    "appSecret": "secret123",
                },
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        ch = channels[0]
        assert ch.name == "feishu:plato"
        assert ch.enabled is True
        assert ch.settings["appId"] == "cli_abc123"
        assert ch.settings["appSecret"] == "secret123"

    def test_multiple_feishu_channels(self) -> None:
        payload = [
            {
                "name": "feishu:plato",
                "settings": {"appId": "cli_a", "appSecret": "s_a"},
            },
            {
                "name": "feishu:luban",
                "settings": {"appId": "cli_b", "appSecret": "s_b"},
            },
            {
                "name": "feishu:hume",
                "settings": {"appId": "cli_c", "appSecret": "s_c"},
            },
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 3
        names = [ch.name for ch in channels]
        assert names == ["feishu:plato", "feishu:luban", "feishu:hume"]

    def test_disabled_feishu_channel_excluded(self) -> None:
        payload = [
            {
                "name": "feishu:plato",
                "settings": {"appId": "cli_a", "appSecret": "s_a"},
            },
            {
                "name": "feishu:luban",
                "enabled": False,
                "settings": {"appId": "cli_b", "appSecret": "s_b"},
            },
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        assert channels[0].name == "feishu:plato"

    def test_missing_app_id_raises(self) -> None:
        payload = [
            {
                "name": "feishu:plato",
                "settings": {"appSecret": "secret"},
            }
        ]
        with pytest.raises(ValueError, match="appId"):
            _parse_channels(payload)

    def test_missing_app_secret_raises(self) -> None:
        payload = [
            {
                "name": "feishu:plato",
                "settings": {"appId": "cli_a"},
            }
        ]
        with pytest.raises(ValueError, match="appSecret"):
            _parse_channels(payload)

    def test_empty_feishu_name_suffix_raises(self) -> None:
        """A feishu channel name must contain an agent id after the colon."""
        payload = [
            {
                "name": "feishu:",
                "settings": {"appId": "cli_a", "appSecret": "secret"},
            }
        ]
        # The adapter will reject this at construction time; the parser lets it
        # through because validation happens on settings only.
        channels = _parse_channels(payload)
        assert len(channels) == 1
        assert channels[0].name == "feishu:"

    def test_feishu_combined_with_other_channels(self) -> None:
        """feishu channels + regular channel entries coexist."""
        payload = [
            {"name": "web_relay"},
            {
                "name": "feishu:plato",
                "settings": {"appId": "cli_a", "appSecret": "s_a"},
            },
        ]
        channels = _parse_channels(payload)
        names = [ch.name for ch in channels]
        assert "web_relay" in names
        assert "feishu:plato" in names
        assert len(channels) == 2

    def test_none_payload_returns_empty(self) -> None:
        assert _parse_channels(None) == ()

    def test_feishu_channel_with_bot_open_id_preserved(self) -> None:
        """botOpenId in settings is preserved for adapter mention detection."""
        payload = [
            {
                "name": "feishu:plato",
                "settings": {
                    "appId": "cli_abc",
                    "appSecret": "sec",
                    "botOpenId": "ou_bot_123",
                },
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        settings = channels[0].settings
        assert settings["botOpenId"] == "ou_bot_123"

    def test_feishu_channel_without_bot_open_id_omits_key(self) -> None:
        """When botOpenId is absent, settings does not contain the key."""
        payload = [
            {
                "name": "feishu:plato",
                "settings": {"appId": "cli_abc", "appSecret": "sec"},
            }
        ]
        channels = _parse_channels(payload)
        assert "botOpenId" not in channels[0].settings

    def test_feishu_top_level_enabled_false_skips(self) -> None:
        """feishu channel with enabled: false should not be returned."""
        payload = [
            {
                "name": "feishu:plato",
                "enabled": False,
                "settings": {"appId": "cli_abc", "appSecret": "sec"},
            }
        ]
        channels = _parse_channels(payload)
        assert channels == ()

    def test_feishu_top_level_enabled_true_parses(self) -> None:
        """feishu channel with enabled: true (explicit) should parse normally."""
        payload = [
            {
                "name": "feishu:plato",
                "enabled": True,
                "settings": {"appId": "cli_abc", "appSecret": "sec"},
            }
        ]
        channels = _parse_channels(payload)
        assert len(channels) == 1
        assert channels[0].name == "feishu:plato"
