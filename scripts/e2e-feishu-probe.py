#!/usr/bin/env python3
"""Prove one isolated Gateway receives a user message from the test Feishu Bot."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from e2e_feishu_config import FeishuE2EConfigError, load_e2e_env


def _default_e2e_env_path() -> Path:
    """Return the private profile path using the same XDG rule as the launcher."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "nano-multiagent" / "feishu-e2e.env"


def _profile_status(profile: str) -> dict[str, object]:
    """Return verified status for the explicitly selected lark-cli profile."""
    try:
        result = subprocess.run(
            ["lark-cli", "--profile", profile, "auth", "status", "--json", "--verify"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("lark-cli is required for the Feishu E2E probe") from exc
    if result.returncode != 0:
        raise RuntimeError("the selected lark-cli profile is not verified")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("lark-cli did not return profile status JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("lark-cli returned an invalid profile status")
    return payload


def _require_test_profile(
    status: dict[str, object], values: dict[str, str], profile: str
) -> None:
    """Reject default, unverified, or cross-App profiles before sending a probe."""
    if not profile or profile == "default" or status.get("verified") is not True:
        raise RuntimeError(
            "a verified, non-default dedicated lark-cli profile is required"
        )
    if status.get("appId") != values["NANO_MULTIAGENT_E2E_FEISHU_APP_ID"]:
        raise RuntimeError(
            "the selected lark-cli profile belongs to a different Feishu App"
        )
    identities = status.get("identities")
    bot = identities.get("bot") if isinstance(identities, dict) else None
    if not isinstance(bot, dict) or bot.get("verified") is not True:
        raise RuntimeError(
            "the selected lark-cli profile cannot verify its Bot identity"
        )
    if bot.get("openId") != values["NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID"]:
        raise RuntimeError("the selected lark-cli profile targets a different Bot")


def _saga_count(path: Path) -> int:
    """Return the durable external-inbound count, treating startup as zero."""
    if not path.is_file():
        return 0
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM external_shadow_sagas"
            ).fetchone()
    except sqlite3.Error:
        return 0
    return int(row[0]) if row else 0


def _require_feishu_stack(worktree: Path) -> None:
    """Ensure the probe cannot send through a non-Feishu E2E worktree."""
    ports_env = worktree / ".e2e-ports.env"
    if not ports_env.is_file():
        raise RuntimeError("the target worktree has no active E2E stack")
    if "export E2E_PROFILE=feishu" not in ports_env.read_text(encoding="utf-8"):
        raise RuntimeError("the target worktree was not started with --feishu")


def _send_probe(profile: str, bot_open_id: str) -> None:
    """Send one nonce through the selected test App as its verified test user."""
    nonce = f"nano-e2e-feishu-probe-{secrets.token_hex(8)}"
    result = subprocess.run(
        [
            "lark-cli",
            "--profile",
            profile,
            "im",
            "+messages-send",
            "--as",
            "user",
            "--user-id",
            bot_open_id,
            "--text",
            nonce,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("lark-cli could not send the Feishu E2E probe")


def main() -> int:
    """Run one dedicated-App ingress probe against a running isolated worktree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wt", required=True, type=Path)
    parser.add_argument(
        "--env",
        type=Path,
        default=_default_e2e_env_path(),
    )
    parser.add_argument("--profile")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    try:
        values = load_e2e_env(args.env)
        profile = args.profile or values.get(
            "NANO_MULTIAGENT_E2E_FEISHU_LARK_PROFILE", ""
        )
        _require_test_profile(_profile_status(profile), values, profile)
        _require_feishu_stack(args.wt)
        before = _saga_count(args.wt / "external_shadow_sagas.sqlite3")
        _send_probe(profile, values["NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID"])
    except (FeishuE2EConfigError, RuntimeError) as exc:
        parser.error(str(exc))

    deadline = time.monotonic() + args.timeout
    saga_path = args.wt / "external_shadow_sagas.sqlite3"
    while time.monotonic() < deadline:
        if _saga_count(saga_path) > before:
            print(f"Feishu E2E ingress probe passed (profile={profile})")
            return 0
        time.sleep(0.25)
    parser.error("Feishu E2E probe message was not received by the isolated Gateway")


if __name__ == "__main__":
    sys.exit(main())
