"""Regression coverage for the migration backup commit guard."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import threading

import pytest

from personal_assistant.config.local_store import load_local_config, save_local_config


_LLM_YAML = """\
llm:
  default_model: test:model
  providers:
    - name: test
      base_url: http://127.0.0.1:4000
      models:
        - name: test:model
"""


def _legacy_config(tmp_path: Path) -> tuple[Path, bytes]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "config.yaml"
    original = (
        "\n".join(
            [
                "node:",
                "  node_id: backup-guard-test",
                "agents:",
                "  - agent_id: assistant",
                f"    workspace_root: {workspace}",
                "kernel:",
                "  startup_timeout_seconds: 2",
            ]
        )
        + "\n"
        + _LLM_YAML
    ).encode()
    config_path.write_bytes(original)
    config_path.chmod(0o640)
    return config_path, original


@pytest.mark.parametrize("backup_exists", [False, True])
@pytest.mark.parametrize("drift", ["content", "mode"])
def test_in_place_backup_drift_before_commit_preserves_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    backup_exists: bool,
    drift: str,
) -> None:
    config_path, original = _legacy_config(tmp_path)
    backup_path = Path(f"{config_path}.pre-refactor-461.bak")
    if backup_exists:
        backup_path.write_bytes(original)
        backup_path.chmod(0o640)

    backup_durable = threading.Event()
    drift_done = threading.Event()
    real_fsync = os.fsync

    def _fsync_with_drift_barrier(fd: int) -> None:
        real_fsync(fd)
        if (
            backup_path.exists()
            and stat.S_ISDIR(os.fstat(fd).st_mode)
            and not backup_durable.is_set()
        ):
            backup_durable.set()
            assert drift_done.wait(timeout=2)

    def _drift_backup() -> None:
        assert backup_durable.wait(timeout=2)
        if drift == "content":
            backup_path.write_bytes(b"x" * len(original))
        else:
            backup_path.chmod(0o600)
        drift_done.set()

    monkeypatch.setattr(os, "fsync", _fsync_with_drift_barrier)
    writer = threading.Thread(target=_drift_backup)
    writer.start()
    try:
        with pytest.raises(FileExistsError, match="backup.*changed"):
            save_local_config(load_local_config(config_path), config_path)
    finally:
        writer.join(timeout=2)

    assert not writer.is_alive()
    assert config_path.read_bytes() == original
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o640
