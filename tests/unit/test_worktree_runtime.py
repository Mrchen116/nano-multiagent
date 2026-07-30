from __future__ import annotations

from pathlib import Path

from agent.platform.worktree_runtime import prepare_shared_runtime_files


def test_prepare_shared_runtime_files_converts_lock_dir_to_repo_symlink(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_data = repo_root / "data"
    repo_data.mkdir(parents=True)
    shared_locks = repo_data / "locks"
    shared_locks.mkdir()
    (shared_locks / "merge.lock").write_text("", encoding="utf-8")

    worktree_dir = repo_root / ".worktrees" / "M139"
    worktree_data = worktree_dir / "data"
    worktree_data.mkdir(parents=True)
    local_locks = worktree_data / "locks"
    local_locks.mkdir()
    (local_locks / "merge.lock").write_text("stale", encoding="utf-8")

    prepare_shared_runtime_files(repo_root=repo_root, worktree_dir=worktree_dir)

    assert local_locks.is_symlink()
    assert local_locks.resolve() == shared_locks.resolve()


def test_prepare_shared_runtime_files_is_idempotent_for_existing_lock_symlink(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_data = repo_root / "data"
    repo_data.mkdir(parents=True)
    shared_locks = repo_data / "locks"
    shared_locks.mkdir()

    worktree_dir = repo_root / ".worktrees" / "M139"
    worktree_data = worktree_dir / "data"
    worktree_data.mkdir(parents=True)
    local_locks = worktree_data / "locks"
    local_locks.symlink_to(shared_locks, target_is_directory=True)

    prepare_shared_runtime_files(repo_root=repo_root, worktree_dir=worktree_dir)

    assert local_locks.is_symlink()
    assert local_locks.resolve() == shared_locks.resolve()


def test_prepare_shared_runtime_files_recreates_worktree_local_data_dir_for_private_runtime_files(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_data = repo_root / "data"
    repo_data.mkdir(parents=True)
    shared_locks = repo_data / "locks"
    shared_locks.mkdir()

    worktree_dir = repo_root / ".worktrees" / "M175"

    prepare_shared_runtime_files(repo_root=repo_root, worktree_dir=worktree_dir)

    worktree_data = worktree_dir / "data"
    assert worktree_data.is_dir()
    assert not worktree_data.is_symlink()
    assert (worktree_data / "locks").is_symlink()
    assert (worktree_data / "locks").resolve() == shared_locks.resolve()
