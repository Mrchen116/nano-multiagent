#!/usr/bin/env python3
"""Export the encrypted channel cache to an explicit legacy Gateway YAML file."""

from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from personal_assistant.channels.channel_credentials import (  # noqa: E402
    GatewayChannelAad,
    GatewayChannelKeyStore,
)
from personal_assistant.config.local_store import (  # noqa: E402
    ChannelConfig,
    load_local_config,
    save_local_config,
)
from personal_assistant.gateway.channel_manifest_store import (  # noqa: E402
    ChannelManifestStore,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = load_local_config(args.config)
    key = GatewayChannelKeyStore(args.key).load_or_create()
    store = ChannelManifestStore(
        args.cache,
        node_id=config.node.node_id,
        key_id=key.key_id,
    )
    manifest = store.load_manifest()
    if manifest is None:
        raise SystemExit("channel manifest cache is empty")

    exported_by_name: dict[str, ChannelConfig] = {}
    for item in manifest.channels:
        aad = GatewayChannelAad(
            owner_id=manifest.owner_id,
            node_id=manifest.node_id,
            agent_id=item.agent_id,
            channel_id=item.channel_id,
            provider=item.provider,
            credential_revision=item.credential_revision,
        )
        secret = key.open(envelope=item.credential_envelope, aad=aad)
        settings: dict[str, object] = {
            "appId": str(item.config.get("app_id") or ""),
            "appSecret": secret["app_secret"],
        }
        owner_open_id = item.provider_runtime.get("owner_open_id")
        bot_open_id = item.provider_runtime.get("bot_open_id")
        if owner_open_id:
            settings["ownerOpenId"] = owner_open_id
        if bot_open_id:
            settings["botOpenId"] = bot_open_id
        name = f"{item.provider}:{item.agent_id}"
        exported_by_name[name] = ChannelConfig(
            name=name,
            enabled=item.enabled,
            settings=settings,
        )

    channels: list[ChannelConfig] = []
    for channel in config.channels:
        replacement = exported_by_name.pop(channel.name, None)
        channels.append(replacement or channel)
    channels.extend(exported_by_name.values())
    output_config = replace(config, channels=tuple(channels), source_path=args.output)
    save_local_config(output_config, args.output)
    os.chmod(args.output, 0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
