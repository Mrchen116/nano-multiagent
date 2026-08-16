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
from typing import Any

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


def _lark_json(profile: str, *args: str) -> dict[str, Any]:
    """Run one dedicated-profile Lark command and return its successful envelope."""

    result = subprocess.run(
        ["lark-cli", "--profile", profile, *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
            "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
        },
    )
    if result.returncode != 0:
        raise RuntimeError("dedicated lark-cli profile command failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("dedicated lark-cli profile returned invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("dedicated lark-cli profile returned a failed envelope")
    return payload


def _send_probe(profile: str, bot_open_id: str) -> tuple[str, str]:
    """Send one nonce and return it with the target chat identity."""

    nonce = f"nano-e2e-feishu-probe-{secrets.token_hex(8)}"
    payload = _lark_json(
        profile,
        "im",
        "+messages-send",
        "--as",
        "user",
        "--user-id",
        bot_open_id,
        "--text",
        nonce,
        "--idempotency-key",
        secrets.token_hex(12),
    )
    data = payload.get("data")
    chat_id = data.get("chat_id") if isinstance(data, dict) else None
    if not isinstance(chat_id, str) or not chat_id:
        raise RuntimeError("Feishu E2E probe send did not return a chat id")
    return nonce, chat_id


def _lark_messages(profile: str, chat_id: str) -> list[dict[str, Any]]:
    """Read the dedicated test chat as the verified test user."""

    payload = _lark_json(
        profile,
        "im",
        "+chat-messages-list",
        "--as",
        "user",
        "--chat-id",
        chat_id,
        "--page-size",
        "50",
        "--no-reactions",
    )
    data = payload.get("data")
    messages = data.get("messages") if isinstance(data, dict) else None
    return [item for item in messages or [] if isinstance(item, dict)]


def _runtime_card_messages(
    messages: list[dict[str, Any]], nonce: str
) -> list[dict[str, Any]]:
    """Select final runtime cards bound to this probe's unique nonce."""

    matches: list[dict[str, Any]] = []
    for message in messages:
        message_type = message.get("msg_type") or message.get("message_type")
        content = message.get("content")
        if message_type != "interactive" or not isinstance(content, str):
            continue
        try:
            card = json.loads(content)
        except json.JSONDecodeError:
            card = {"rendered_content": content}
        if isinstance(card, dict) and nonce in json.dumps(card, ensure_ascii=False):
            matches.append(card)
    return matches


def _shadow_final_content(path: Path, nonce: str) -> str | None:
    """Return the durable plain final shadow content for this probe, if ready."""

    if not path.is_file():
        return None
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                """
                SELECT bubble.content
                FROM external_shadow_sagas AS saga
                JOIN external_shadow_bubbles AS bubble ON bubble.saga_id = saga.saga_id
                WHERE saga.canonical_inbound_json LIKE ?
                  AND bubble.state IN ('ready', 'reconciled')
                  AND bubble.delivery_status = 'completed'
                ORDER BY bubble.bubble_ordinal DESC
                LIMIT 1
                """,
                (f"%{nonce}%",),
            ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]) if row and isinstance(row[0], str) else None


def _card_has_runtime_footer(card: dict[str, Any]) -> bool:
    """Require a compact context label inside the native card payload."""

    return "ctx " in json.dumps(card, ensure_ascii=False)


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
        nonce, chat_id = _send_probe(
            profile, values["NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID"]
        )
    except (FeishuE2EConfigError, RuntimeError) as exc:
        parser.error(str(exc))

    deadline = time.monotonic() + args.timeout
    saga_path = args.wt / "external_shadow_sagas.sqlite3"
    while time.monotonic() < deadline:
        if _saga_count(saga_path) <= before:
            time.sleep(0.25)
            continue
        cards = _runtime_card_messages(_lark_messages(profile, chat_id), nonce)
        shadow_text = _shadow_final_content(saga_path, nonce)
        if (
            len(cards) == 1
            and _card_has_runtime_footer(cards[0])
            and shadow_text
            and "ctx " not in shadow_text
        ):
            print(f"Feishu E2E runtime card probe passed (profile={profile})")
            return 0
        time.sleep(0.25)
    parser.error(
        "Feishu E2E probe did not observe one interactive runtime card and plain shadow"
    )


if __name__ == "__main__":
    sys.exit(main())
