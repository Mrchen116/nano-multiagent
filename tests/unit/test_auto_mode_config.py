"""Tests for AutoModeConfig loading — global/workspace two-level resolution.

Covers:
- Default config when no files exist
- Global config loaded
- Workspace config overrides global
- Partial override (workspace only has some keys)
- dangerously_skip_permissions defaults to False
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from agent.platform.config.auto_mode import AutoModeConfig, load_auto_mode_config


class TestAutoModeConfigDefaults:
    """Default values without any config files."""

    def test_default_enabled(self):
        cfg = AutoModeConfig()
        assert cfg.enabled is True

    def test_default_skip_permissions_false(self):
        cfg = AutoModeConfig()
        assert cfg.dangerously_skip_permissions is False

    def test_default_always_allow_tools_empty(self):
        cfg = AutoModeConfig()
        assert cfg.always_allow_tools == ()

    def test_default_deny_limit(self):
        cfg = AutoModeConfig()
        assert cfg.deny_limit == 3

    def test_default_ask_timeout_sec(self):
        cfg = AutoModeConfig()
        assert cfg.ask_timeout_sec == 600

    def test_default_unattended_fallback(self):
        cfg = AutoModeConfig()
        assert cfg.unattended_fallback == "deny"

    def test_default_allow_rules_empty(self):
        cfg = AutoModeConfig()
        assert cfg.allow == ()

    def test_default_soft_deny_empty(self):
        cfg = AutoModeConfig()
        assert cfg.soft_deny == ()

    def test_default_environment_empty(self):
        cfg = AutoModeConfig()
        assert cfg.environment == ()


class TestLoadAutoModeConfig:
    """load_auto_mode_config integration with filesystem."""

    def test_returns_defaults_when_no_files(self, tmp_path):
        global_dir = tmp_path / "global"
        workspace_dir = tmp_path / "workspace"
        global_dir.mkdir()
        workspace_dir.mkdir()
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=workspace_dir
        )
        assert cfg == AutoModeConfig()

    def test_loads_global_config(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        config_data = {
            "auto_mode": {
                "allow": ["reading files"],
                "soft_deny": ["deleting files"],
                "environment": ["Python project"],
            }
        }
        (global_dir / "config.yaml").write_text(
            yaml.dump(config_data), encoding="utf-8"
        )
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=None
        )
        assert cfg.allow == ("reading files",)
        assert cfg.soft_deny == ("deleting files",)
        assert cfg.environment == ("Python project",)

    def test_workspace_overrides_global(self, tmp_path):
        global_dir = tmp_path / "global"
        workspace_dir = tmp_path / "workspace"
        global_dir.mkdir()
        workspace_dir.mkdir()
        global_data = {
            "auto_mode": {
                "allow": ["global rule"],
                "deny_limit": 5,
            }
        }
        workspace_data = {
            "auto_mode": {
                "allow": ["workspace rule"],
                "dangerously_skip_permissions": True,
            }
        }
        (global_dir / "config.yaml").write_text(
            yaml.dump(global_data), encoding="utf-8"
        )
        (workspace_dir / "config.yaml").write_text(
            yaml.dump(workspace_data), encoding="utf-8"
        )
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=workspace_dir
        )
        # workspace wins on fields it declares
        assert cfg.allow == ("workspace rule",)
        assert cfg.dangerously_skip_permissions is True
        # global value used when workspace doesn't override
        assert cfg.deny_limit == 5

    def test_missing_auto_mode_section_returns_defaults(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "config.yaml").write_text(
            yaml.dump({"other": "stuff"}), encoding="utf-8"
        )
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=None
        )
        assert cfg == AutoModeConfig()

    def test_workspace_config_none_falls_back_to_global(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "config.yaml").write_text(
            yaml.dump({"auto_mode": {"deny_limit": 7}}), encoding="utf-8"
        )
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=None
        )
        assert cfg.deny_limit == 7

    def test_dangerously_skip_permissions_from_config(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "config.yaml").write_text(
            yaml.dump({"auto_mode": {"dangerously_skip_permissions": True}}),
            encoding="utf-8",
        )
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=None
        )
        assert cfg.dangerously_skip_permissions is True

    def test_always_allow_tools_from_config(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "config.yaml").write_text(
            yaml.dump({"auto_mode": {"always_allow_tools": ["my_tool", "other_tool"]}}),
            encoding="utf-8",
        )
        cfg = load_auto_mode_config(
            global_config_dir=global_dir, workspace_config_dir=None
        )
        assert cfg.always_allow_tools == ("my_tool", "other_tool")
