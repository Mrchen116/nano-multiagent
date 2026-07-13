"""Regression tests for the public config migration transaction."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time

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


def test_independent_process_saves_wait_for_stable_sidecar_lock(
    tmp_path: Path,
) -> None:
    """Public saves in separate interpreters must share one transaction lock."""
    config_path, _original = _legacy_config(tmp_path)
    lock_path = Path(f"{config_path}.lock")
    ready_paths = [tmp_path / f"ready-{index}" for index in range(2)]
    done_paths = [tmp_path / f"done-{index}" for index in range(2)]
    code = """
from dataclasses import replace
from pathlib import Path
import sys
from personal_assistant.config.local_store import load_local_config, save_local_config

config_path, node_id, ready_path, done_path = sys.argv[1:]
config = load_local_config(config_path)
config = replace(config, node=replace(config.node, node_id=node_id))
Path(ready_path).write_text("ready")
save_local_config(config, config_path)
Path(done_path).write_text("done")
"""
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                str(config_path),
                f"writer-{index}",
                str(ready_paths[index]),
                str(done_paths[index]),
            ],
            cwd=Path(__file__).parents[3],
            env={**os.environ, "PYTHONPATH": "src"},
        )
        for index in range(2)
    ]
    try:
        deadline = time.monotonic() + 3
        while not all(path.exists() for path in ready_paths):
            assert time.monotonic() < deadline, "child saves did not reach the barrier"
            time.sleep(0.01)

        time.sleep(0.2)
        assert not any(path.exists() for path in done_paths)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        for process in processes:
            process.wait(timeout=3)

    assert all(process.returncode == 0 for process in processes)
    assert all(path.exists() for path in done_paths)
    assert load_local_config(config_path).node.node_id in {"writer-0", "writer-1"}


@pytest.mark.parametrize("backup_exists", [False, True])
def test_backup_path_swap_before_commit_gate_aborts_save(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    backup_exists: bool,
) -> None:
    """The verified backup fd must still name the path at the commit gate."""
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path)
    backup_path = Path(f"{config_path}.pre-refactor-461.bak")
    displaced_path = tmp_path / "displaced-backup"
    replacement = b"replacement backup inode\n"
    if backup_exists:
        backup_path.write_bytes(original)
        backup_path.chmod(0o640)

    backup_durable = threading.Event()
    swap_done = threading.Event()
    real_fsync = local_store.os.fsync

    def _fsync_with_swap_barrier(fd: int) -> None:
        real_fsync(fd)
        if stat.S_ISDIR(os.fstat(fd).st_mode) and not backup_durable.is_set():
            backup_durable.set()
            assert swap_done.wait(timeout=2)

    def _swap_backup_path() -> None:
        assert backup_durable.wait(timeout=2)
        backup_path.replace(displaced_path)
        backup_path.write_bytes(replacement)
        swap_done.set()

    monkeypatch.setattr(local_store.os, "fsync", _fsync_with_swap_barrier)
    swapper = threading.Thread(target=_swap_backup_path)
    swapper.start()
    try:
        with pytest.raises(FileExistsError, match="backup.*changed"):
            save_local_config(load_local_config(config_path), config_path)
    finally:
        swapper.join(timeout=2)

    assert not swapper.is_alive()
    assert config_path.read_bytes() == original
    assert backup_path.read_bytes() == replacement
    assert displaced_path.read_bytes() == original


def test_source_mode_drift_before_commit_aborts_save(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path, mode=0o640)
    regular_fsyncs = 0
    mode_changed = threading.Event()
    real_fsync = local_store.os.fsync

    def _fsync_then_chmod(fd: int) -> None:
        nonlocal regular_fsyncs
        real_fsync(fd)
        if stat.S_ISREG(os.fstat(fd).st_mode):
            regular_fsyncs += 1
            if regular_fsyncs == 2:
                config_path.chmod(0o600)
                mode_changed.set()

    monkeypatch.setattr(local_store.os, "fsync", _fsync_then_chmod)

    with pytest.raises(RuntimeError, match="changed during save"):
        save_local_config(load_local_config(config_path), config_path)

    assert mode_changed.is_set()
    assert config_path.read_bytes() == original
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600


def test_post_replace_directory_fsync_failure_restores_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path, mode=0o640)
    directory_fsyncs = 0
    real_fsync = local_store.os.fsync

    def _fail_commit_directory_fsync(fd: int) -> None:
        nonlocal directory_fsyncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_fsyncs += 1
            if directory_fsyncs == 2:
                raise OSError("commit directory durability failed")
        real_fsync(fd)

    monkeypatch.setattr(local_store.os, "fsync", _fail_commit_directory_fsync)

    with pytest.raises(OSError, match="commit directory durability failed"):
        save_local_config(load_local_config(config_path), config_path)

    assert directory_fsyncs == 3
    assert config_path.read_bytes() == original
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o640


def test_post_replace_rollback_failure_has_distinct_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import personal_assistant.config.local_store as local_store

    config_path, original = _legacy_config(tmp_path)
    directory_fsyncs = 0
    config_replaces = 0
    real_fsync = local_store.os.fsync
    real_replace = local_store.os.replace

    def _fail_commit_directory_fsync(fd: int) -> None:
        nonlocal directory_fsyncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_fsyncs += 1
            if directory_fsyncs == 2:
                raise OSError("commit directory durability failed")
        real_fsync(fd)

    def _fail_rollback_replace(source: Path, dest: Path) -> None:
        nonlocal config_replaces
        if Path(dest) == config_path:
            config_replaces += 1
            if config_replaces == 2:
                raise OSError("rollback replace failed")
        real_replace(source, dest)

    monkeypatch.setattr(local_store.os, "fsync", _fail_commit_directory_fsync)
    monkeypatch.setattr(local_store.os, "replace", _fail_rollback_replace)

    with pytest.raises(RuntimeError, match="rollback failed"):
        save_local_config(load_local_config(config_path), config_path)

    assert config_replaces == 2
    assert config_path.read_bytes() != original
