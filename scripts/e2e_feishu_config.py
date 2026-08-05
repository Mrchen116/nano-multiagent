#!/usr/bin/env python3
"""Render dedicated Feishu test credentials into one isolated E2E config."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path


class FeishuE2EConfigError(ValueError):
    """Raised when the local Feishu E2E profile cannot be safely rendered."""


_REQUIRED_ENV_KEYS = (
    "NANO_MULTIAGENT_E2E_FEISHU_APP_ID",
    "NANO_MULTIAGENT_E2E_FEISHU_APP_SECRET",
    "NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID",
)
_CHANNEL_NAME = "feishu:e2e"


def load_e2e_env(path: Path) -> dict[str, str]:
    """Read literal ``KEY=VALUE`` entries from the private local E2E env file."""
    if not path.is_file():
        raise FeishuE2EConfigError(f"private E2E env file is missing: {path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or not value:
            raise FeishuE2EConfigError(
                f"invalid private E2E env entry at line {line_number}"
            )
        values[key] = value

    missing = [key for key in _REQUIRED_ENV_KEYS if not values.get(key)]
    if missing:
        raise FeishuE2EConfigError(
            "private E2E env file is missing required Feishu credentials"
        )
    return values


def render_feishu_config(
    config_path: Path,
    values: Mapping[str, str],
    *,
    identity_lookup: Callable[[str, str, str], str | None] | None = None,
) -> None:
    """Inject verified test-App settings into a worktree-local Feishu config."""
    import yaml

    if identity_lookup is None:
        from personal_assistant.config.local_store import (
            infer_feishu_bot_open_id_from_app_credentials,
        )

        identity_lookup = infer_feishu_bot_open_id_from_app_credentials
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, MutableMapping):
        raise FeishuE2EConfigError("Feishu E2E config must be a YAML mapping")
    channels = payload.get("channels")
    if not isinstance(channels, list):
        raise FeishuE2EConfigError("Feishu E2E config must define channels")

    matched = [
        channel
        for channel in channels
        if isinstance(channel, MutableMapping) and channel.get("name") == _CHANNEL_NAME
    ]
    if len(matched) != 1:
        raise FeishuE2EConfigError(
            f"Feishu E2E config must define exactly one {_CHANNEL_NAME} channel"
        )

    app_id = values["NANO_MULTIAGENT_E2E_FEISHU_APP_ID"]
    app_secret = values["NANO_MULTIAGENT_E2E_FEISHU_APP_SECRET"]
    expected_bot_open_id = values["NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID"]
    actual_bot_open_id = identity_lookup(app_id, app_secret, "https://open.feishu.cn")
    if actual_bot_open_id != expected_bot_open_id:
        raise FeishuE2EConfigError(
            "private E2E credentials do not identify the configured test Bot"
        )

    matched[0]["enabled"] = True
    matched[0]["settings"] = {
        "appId": app_id,
        "appSecret": app_secret,
        "botOpenId": expected_bot_open_id,
    }
    config_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    os.chmod(config_path, 0o600)


def main() -> int:
    """Render the private credentials into an isolated Gateway config path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--env", required=True, type=Path)
    args = parser.parse_args()
    try:
        render_feishu_config(args.config, load_e2e_env(args.env))
    except FeishuE2EConfigError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
