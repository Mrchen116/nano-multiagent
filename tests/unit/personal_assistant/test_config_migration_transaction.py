"""Regression tests for the public config migration transaction."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys
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


def _legacy_config(tmp_path: Path, *, mode: int = 0o640) -> tuple[Path, bytes]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "config.yaml"
    original = (
        "\n".join(
            [
                "node:",
                "  node_id: transaction-test",
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
    config_path.chmod(mode)
    return config_path, original


def test_existing_fifo_backup_is_rejected_without_blocking(tmp_path: Path) -> None:
    """A hostile FIFO at the deterministic backup path must fail fast."""
    config_path, original = _legacy_config(tmp_path)
    backup_path = Path(f"{config_path}.pre-refactor-461.bak")
    os.mkfifo(backup_path)
    code = """
from personal_assistant.config.local_store import load_local_config, save_local_config
import sys
path = sys.argv[1]
save_local_config(load_local_config(path), path)
"""

    result = subprocess.run(
        [sys.executable, "-c", code, str(config_path)],
        cwd=Path(__file__).parents[3],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )

    assert result.returncode != 0
    assert "not a regular file" in result.stderr
    assert config_path.read_bytes() == original


def test_existing_backup_with_third_party_hardlink_is_rejected(
    tmp_path: Path,
) -> None:
    config_path, original = _legacy_config(tmp_path)
    backup_path = Path(f"{config_path}.pre-refactor-461.bak")
    backup_path.write_bytes(original)
    witness_path = tmp_path / "third-party-link"
    os.link(backup_path, witness_path)

    with pytest.raises(FileExistsError, match="single-link"):
        save_local_config(load_local_config(config_path), config_path)

    assert config_path.read_bytes() == original
    assert witness_path.read_bytes() == original


def test_new_backup_rejects_hardlink_attached_during_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path)
    backup_path = Path(f"{config_path}.pre-refactor-461.bak")
    witness_path = tmp_path / "third-party-link"
    real_open = local_store.os.open

    def _attach_link_after_open(
        path: str | bytes | os.PathLike[str], flags: int, *args: int
    ) -> int:
        fd = real_open(path, flags, *args)
        if Path(path) == backup_path:
            os.link(backup_path, witness_path)
        return fd

    monkeypatch.setattr(local_store.os, "open", _attach_link_after_open)

    with pytest.raises(FileExistsError, match="single-link"):
        save_local_config(load_local_config(config_path), config_path)

    assert config_path.read_bytes() == original
    assert witness_path.read_bytes() == b""


def test_external_writer_drift_after_backup_gate_aborts_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path)
    backup_path = Path(f"{config_path}.pre-refactor-461.bak")
    external = b"external writer owns this revision\n"
    backup_durable = threading.Event()
    writer_done = threading.Event()
    real_fsync = local_store.os.fsync

    def _fsync_with_barrier(fd: int) -> None:
        real_fsync(fd)
        if (
            backup_path.exists()
            and stat.S_ISDIR(os.fstat(fd).st_mode)
            and not backup_durable.is_set()
        ):
            backup_durable.set()
            assert writer_done.wait(timeout=2)

    def _external_writer() -> None:
        assert backup_durable.wait(timeout=2)
        config_path.write_bytes(external)
        writer_done.set()

    monkeypatch.setattr(local_store.os, "fsync", _fsync_with_barrier)
    writer = threading.Thread(target=_external_writer)
    writer.start()
    try:
        with pytest.raises(RuntimeError, match="changed during save"):
            save_local_config(load_local_config(config_path), config_path)
    finally:
        writer.join(timeout=2)

    assert not writer.is_alive()
    assert config_path.read_bytes() == external
    assert backup_path.read_bytes() == original


def test_atomic_replace_failure_preserves_source_and_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path, mode=0o640)
    config = load_local_config(config_path)
    monkeypatch.setattr(
        local_store.os,
        "replace",
        lambda _source, _dest: (_ for _ in ()).throw(OSError("replace failed")),
    )

    with pytest.raises(OSError, match="replace failed"):
        save_local_config(config, config_path)

    assert config_path.read_bytes() == original
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o640
