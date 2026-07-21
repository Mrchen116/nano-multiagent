"""Atomic local writes for configurations that may contain plaintext secrets."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from personal_assistant.config.local_store import (
    load_local_config,
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
