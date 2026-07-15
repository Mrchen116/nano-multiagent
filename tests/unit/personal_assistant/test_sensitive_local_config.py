"""Atomic local writes for configurations that may contain plaintext secrets."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import stat

import pytest

from personal_assistant.config.local_store import (
    load_local_config,
    migrate_managed_channels_to_credential_refs,
    save_sensitive_local_config,
)


def _legacy_config(path: Path, workspace: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "node:",
                "  node_id: node-a",
                "agents:",
                "  - agent_id: agent-a",
                f"    workspace_root: {workspace}",
                "channels:",
                "  - name: feishu:agent-a",
                "    settings:",
                "      appId: cli_a",
                "      appSecret: legacy-plaintext-secret",
                "llm:",
                "  default_model: test:model",
                "  providers:",
                "    - name: test",
                "      models:",
                "        - name: test:model",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_sensitive_migration_is_atomic_0600_and_skips_plaintext_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing a legacy secret never copies it into the normal backup directory."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    path = home / ".nano-assistant" / "config.yaml"
    _legacy_config(path, tmp_path / "workspace")
    os.chmod(path, 0o644)
    config = load_local_config(path)
    migrated = migrate_managed_channels_to_credential_refs(
        config.channels,
        credential_refs={"feishu:agent-a": "channel-manifest:ch-a"},
    )

    save_sensitive_local_config(replace(config, channels=migrated), path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "legacy-plaintext-secret" not in path.read_text(encoding="utf-8")
    backups = list((path.parent / "backups").glob("*.bak"))
    assert backups == []
    assert list(path.parent.glob(".config.yaml.*.tmp")) == []


def test_sensitive_write_failure_preserves_destination_and_removes_temp_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed atomic replace leaves no secret-bearing temp or modified destination."""
    path = tmp_path / "config.yaml"
    _legacy_config(path, tmp_path / "workspace")
    original = path.read_bytes()
    config = load_local_config(path)

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        save_sensitive_local_config(config, path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob(".config.yaml.*.tmp")) == []
