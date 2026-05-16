"""Tests for AutoModeConfig.web_fetch field (bugfix-355 M3 R2).

Design ref: bugfix-355 design.md 锚点 I (G8):
- New WebFetchConfig dataclass (frozen)
- AutoModeConfig gains web_fetch: WebFetchConfig field
- _parse_auto_mode_config handles nested web_fetch dict
- load_auto_mode_config merges workspace > global at web_fetch level (whole-section override)
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest


class TestWebFetchConfig:
    """WebFetchConfig dataclass defaults and field types."""

    def test_default_all_empty(self):
        from agent.platform.config.auto_mode import WebFetchConfig  # noqa: PLC0415
        cfg = WebFetchConfig()
        assert cfg.preapproved_hosts_extra == ()
        assert cfg.deny_hosts == ()
        assert cfg.ask_hosts == ()
        assert cfg.allow_hosts == ()

    def test_with_values(self):
        from agent.platform.config.auto_mode import WebFetchConfig  # noqa: PLC0415
        cfg = WebFetchConfig(
            preapproved_hosts_extra=("mycompany.com",),
            deny_hosts=("evil.com",),
            ask_hosts=("confirm.io",),
            allow_hosts=("example.org",),
        )
        assert "mycompany.com" in cfg.preapproved_hosts_extra
        assert "evil.com" in cfg.deny_hosts
        assert "confirm.io" in cfg.ask_hosts
        assert "example.org" in cfg.allow_hosts

    def test_is_frozen(self):
        from agent.platform.config.auto_mode import WebFetchConfig  # noqa: PLC0415
        cfg = WebFetchConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.allow_hosts = ("x.com",)  # type: ignore[misc]


class TestAutoModeConfigWebFetchField:
    """AutoModeConfig gains web_fetch: WebFetchConfig field."""

    def test_default_web_fetch_field(self):
        from agent.platform.config.auto_mode import AutoModeConfig, WebFetchConfig  # noqa: PLC0415
        cfg = AutoModeConfig()
        assert hasattr(cfg, "web_fetch")
        assert isinstance(cfg.web_fetch, WebFetchConfig)

    def test_web_fetch_defaults_are_empty(self):
        from agent.platform.config.auto_mode import AutoModeConfig  # noqa: PLC0415
        cfg = AutoModeConfig()
        assert cfg.web_fetch.deny_hosts == ()
        assert cfg.web_fetch.allow_hosts == ()


class TestParseAutoModeConfigWebFetch:
    """_parse_auto_mode_config handles web_fetch nested dict."""

    def _parse(self, raw: dict):
        from agent.platform.config.auto_mode import _parse_auto_mode_config  # noqa: PLC0415
        return _parse_auto_mode_config(raw)

    def test_no_web_fetch_key_gives_defaults(self):
        cfg = self._parse({})
        assert cfg.web_fetch.allow_hosts == ()
        assert cfg.web_fetch.deny_hosts == ()

    def test_web_fetch_allow_hosts_parsed(self):
        cfg = self._parse({"web_fetch": {"allow_hosts": ["example.org", "trusted.com"]}})
        assert cfg.web_fetch.allow_hosts == ("example.org", "trusted.com")

    def test_web_fetch_deny_hosts_parsed(self):
        cfg = self._parse({"web_fetch": {"deny_hosts": ["evil.com"]}})
        assert cfg.web_fetch.deny_hosts == ("evil.com",)

    def test_web_fetch_ask_hosts_parsed(self):
        cfg = self._parse({"web_fetch": {"ask_hosts": ["review.me"]}})
        assert cfg.web_fetch.ask_hosts == ("review.me",)

    def test_web_fetch_preapproved_extra_parsed(self):
        cfg = self._parse({"web_fetch": {"preapproved_hosts_extra": ["internal.company.com"]}})
        assert cfg.web_fetch.preapproved_hosts_extra == ("internal.company.com",)

    def test_web_fetch_invalid_type_falls_to_defaults(self):
        """Non-Mapping web_fetch value → treated as empty → defaults."""
        cfg = self._parse({"web_fetch": "not-a-dict"})
        assert cfg.web_fetch.allow_hosts == ()

    def test_web_fetch_none_falls_to_defaults(self):
        cfg = self._parse({"web_fetch": None})
        assert cfg.web_fetch.deny_hosts == ()

    def test_existing_fields_unaffected(self):
        """Adding web_fetch must not break existing AutoModeConfig fields."""
        cfg = self._parse({
            "enabled": False,
            "deny_limit": 5,
            "web_fetch": {"allow_hosts": ["x.com"]},
        })
        assert cfg.enabled is False
        assert cfg.deny_limit == 5
        assert cfg.web_fetch.allow_hosts == ("x.com",)


class TestLoadAutoModeConfigWebFetch:
    """YAML load + workspace > global merge for web_fetch section."""

    def _write_config(self, config_dir: Path, content: str) -> None:
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(textwrap.dedent(content), encoding="utf-8")

    def test_yaml_web_fetch_allow_hosts(self):
        from agent.platform.config.auto_mode import load_auto_mode_config  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            global_dir = Path(tmp) / "global"
            self._write_config(global_dir, """
                auto_mode:
                  web_fetch:
                    allow_hosts:
                      - example.org
            """)
            cfg = load_auto_mode_config(global_config_dir=global_dir, workspace_config_dir=None)
            assert "example.org" in cfg.web_fetch.allow_hosts

    def test_workspace_overrides_global_web_fetch(self):
        """Workspace web_fetch section wholly overrides global (simple merge)."""
        from agent.platform.config.auto_mode import load_auto_mode_config  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            global_dir = Path(tmp) / "global"
            workspace_dir = Path(tmp) / "workspace"
            self._write_config(global_dir, """
                auto_mode:
                  web_fetch:
                    deny_hosts:
                      - blocked-global.com
                    allow_hosts:
                      - global-allowed.org
            """)
            self._write_config(workspace_dir, """
                auto_mode:
                  web_fetch:
                    allow_hosts:
                      - workspace-allowed.org
            """)
            cfg = load_auto_mode_config(
                global_config_dir=global_dir,
                workspace_config_dir=workspace_dir,
            )
            # workspace web_fetch wholly replaces global web_fetch
            assert "workspace-allowed.org" in cfg.web_fetch.allow_hosts
            # global allow_hosts replaced by workspace's (simple section-level merge)
            assert "global-allowed.org" not in cfg.web_fetch.allow_hosts

    def test_no_web_fetch_in_yaml_gives_defaults(self):
        from agent.platform.config.auto_mode import load_auto_mode_config  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            global_dir = Path(tmp) / "global"
            self._write_config(global_dir, """
                auto_mode:
                  enabled: true
            """)
            cfg = load_auto_mode_config(global_config_dir=global_dir, workspace_config_dir=None)
            assert cfg.web_fetch.allow_hosts == ()
            assert cfg.web_fetch.deny_hosts == ()
