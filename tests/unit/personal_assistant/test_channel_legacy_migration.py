"""Legacy YAML migration and explicit rollback export coverage."""

from __future__ import annotations

import json
from pathlib import Path
import stat
import subprocess
import sys

import yaml

from personal_assistant.channels.channel_credentials import (
    GatewayChannelAad,
    GatewayChannelKeyStore,
)
from personal_assistant.config.local_store import (
    ChannelConfig,
    migrate_managed_channels_to_credential_refs,
)
from personal_assistant.gateway.channel_manager import (
    ChannelGeneration,
    ChannelManifest,
    ManagedChannelSpec,
)
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore


def test_migration_replaces_only_managed_secret_after_authoritative_cache() -> None:
    """Migration keeps static relay and non-sensitive provider metadata."""
    channels = (
        ChannelConfig(name="web_relay"),
        ChannelConfig(
            name="feishu:agent-a",
            settings={
                "appId": "cli_legacy",
                "appSecret": "legacy-secret",
                "ownerOpenId": "ou-owner",
            },
        ),
    )

    migrated = migrate_managed_channels_to_credential_refs(
        channels,
        credential_refs={"feishu:agent-a": "channel-manifest:ch-a"},
    )

    assert migrated[0] == channels[0]
    assert migrated[1].settings == {
        "appId": "cli_legacy",
        "ownerOpenId": "ou-owner",
        "credentialRef": "channel-manifest:ch-a",
    }
    assert channels[1].settings["appSecret"] == "legacy-secret"


def test_export_legacy_cli_opens_cache_to_explicit_mode_0600_file(
    tmp_path: Path,
) -> None:
    """Rollback export never writes plaintext to stdout or a permissive file."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-a",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace}",
                "channels:",
                "  - name: web_relay",
                "  - name: feishu:agent-a",
                "    settings:",
                "      appId: cli_legacy",
                "      credentialRef: channel-manifest:ch-a",
                "llm:",
                "  default_model: test:model",
                "  providers:",
                "    - name: test",
                "      base_url: http://127.0.0.1:4000",
                "      models:",
                "        - name: test:model",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    key_path = tmp_path / "channel-credentials-v1.pem"
    key = GatewayChannelKeyStore(key_path).load_or_create()
    aad = GatewayChannelAad(
        owner_id="owner-a",
        node_id="node-a",
        agent_id="agent-a",
        channel_id="ch-a",
        provider="feishu",
        credential_revision=1,
    )
    envelope = key.seal(
        secret={"app_secret": "rollback-secret"},
        aad=aad,
    )
    store = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json",
        node_id="node-a",
        key_id=key.key_id,
    )
    store.commit_manifest(
        ChannelManifest(
            owner_id="owner-a",
            node_id="node-a",
            manifest_revision=1,
            channels=(
                ManagedChannelSpec(
                    channel_id="ch-a",
                    agent_id="agent-a",
                    provider="feishu",
                    enabled=True,
                    config={"app_id": "cli_legacy"},
                    credentials={"app_secret": "must-not-persist"},
                    provider_runtime={"owner_open_id": "ou-owner"},
                    credential_envelope=envelope,
                    credential_key_id=key.key_id,
                    generation=ChannelGeneration(
                        provider_identity_fingerprint="fp-a",
                        provider_identity_revision=1,
                        channel_revision=1,
                        credential_revision=1,
                    ),
                ),
            ),
        )
    )
    output = tmp_path / "legacy-export.yaml"
    script = Path(__file__).resolve().parents[3] / "scripts" / "channel-control-export-legacy.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--config",
            str(config_path),
            "--cache",
            str(tmp_path / "channel-manifest-v1.json"),
            "--key",
            str(key_path),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "rollback-secret" not in completed.stdout
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    exported = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert exported["channels"][1]["settings"] == {
        "appId": "cli_legacy",
        "appSecret": "rollback-secret",
        "ownerOpenId": "ou-owner",
    }
    assert "must-not-persist" not in json.dumps(exported)
