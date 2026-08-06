"""Focused tests for the private Feishu E2E config renderer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml


_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e_feishu_config.py"
_SPEC = importlib.util.spec_from_file_location("e2e_feishu_config", _SCRIPT)
assert _SPEC and _SPEC.loader
e2e_feishu_config = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(e2e_feishu_config)


def _config(path: Path) -> None:
    path.write_text(
        """channels:
  - name: feishu:e2e
    enabled: false
    settings: {}
""",
        encoding="utf-8",
    )


def _values() -> dict[str, str]:
    return {
        "NANO_MULTIAGENT_E2E_FEISHU_APP_ID": "cli_test",
        "NANO_MULTIAGENT_E2E_FEISHU_APP_SECRET": "test-secret",
        "NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID": "ou_test_bot",
    }


def test_render_feishu_config_injects_only_verified_test_identity(
    tmp_path: Path,
) -> None:
    """A matching App identity is rendered only into the isolated config copy."""
    config_path = tmp_path / "gateway.yaml"
    _config(config_path)

    e2e_feishu_config.render_feishu_config(
        config_path,
        _values(),
        identity_lookup=lambda *_: "ou_test_bot",
    )

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["channels"][0]["settings"] == {
        "appId": "cli_test",
        "appSecret": "test-secret",
        "botOpenId": "ou_test_bot",
    }
    assert payload["channels"][0]["enabled"] is True
    assert config_path.stat().st_mode & 0o777 == 0o600


def test_render_feishu_config_rejects_wrong_bot_before_writing(tmp_path: Path) -> None:
    """Wrong credentials cannot start a listener under the dedicated test profile."""
    config_path = tmp_path / "gateway.yaml"
    _config(config_path)

    with pytest.raises(
        e2e_feishu_config.FeishuE2EConfigError,
        match="do not identify the configured test Bot",
    ):
        e2e_feishu_config.render_feishu_config(
            config_path,
            _values(),
            identity_lookup=lambda *_: "ou_other_bot",
        )

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["channels"][0]["settings"] == {}


def test_load_e2e_env_requires_all_feishu_values(tmp_path: Path) -> None:
    """A partial local env file fails before an E2E Gateway can start."""
    env_path = tmp_path / "feishu-e2e.env"
    env_path.write_text(
        "NANO_MULTIAGENT_E2E_FEISHU_APP_ID=cli_test\n", encoding="utf-8"
    )

    with pytest.raises(
        e2e_feishu_config.FeishuE2EConfigError,
        match="missing required Feishu credentials",
    ):
        e2e_feishu_config.load_e2e_env(env_path)
