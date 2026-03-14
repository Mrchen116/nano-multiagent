from __future__ import annotations

from pathlib import Path

from agent.platform.worktree_runtime import prepare_shared_runtime_files


def test_prepare_shared_runtime_files_converts_dev_tasks_file_to_repo_symlink(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_data = repo_root / "data"
    repo_data.mkdir(parents=True)
    shared_board = repo_data / "dev-tasks.json"
    shared_board.write_text('{"board":"shared"}\n', encoding="utf-8")
    shared_locks = repo_data / "locks"
    shared_locks.mkdir()
    (shared_locks / "merge.lock").write_text("", encoding="utf-8")

    worktree_dir = repo_root / ".worktrees" / "M139"
    worktree_data = worktree_dir / "data"
    worktree_data.mkdir(parents=True)
    local_board = worktree_data / "dev-tasks.json"
    local_board.write_text('{"board":"stale-copy"}\n', encoding="utf-8")
    local_locks = worktree_data / "locks"
    local_locks.mkdir()
    (local_locks / "merge.lock").write_text("stale", encoding="utf-8")

    prepare_shared_runtime_files(repo_root=repo_root, worktree_dir=worktree_dir)

    assert local_board.is_symlink()
    assert local_board.resolve() == shared_board.resolve()
    assert local_board.read_text(encoding="utf-8") == '{"board":"shared"}\n'
    assert local_locks.is_symlink()
    assert local_locks.resolve() == shared_locks.resolve()


def test_prepare_shared_runtime_files_is_idempotent_for_existing_symlink(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_data = repo_root / "data"
    repo_data.mkdir(parents=True)
    shared_board = repo_data / "dev-tasks.json"
    shared_board.write_text('{"board":"shared"}\n', encoding="utf-8")
    shared_locks = repo_data / "locks"
    shared_locks.mkdir()

    worktree_dir = repo_root / ".worktrees" / "M139"
    worktree_data = worktree_dir / "data"
    worktree_data.mkdir(parents=True)
    local_board = worktree_data / "dev-tasks.json"
    local_board.symlink_to(shared_board)
    local_locks = worktree_data / "locks"
    local_locks.symlink_to(shared_locks, target_is_directory=True)

    prepare_shared_runtime_files(repo_root=repo_root, worktree_dir=worktree_dir)

    assert local_board.is_symlink()
    assert local_board.resolve() == shared_board.resolve()
    assert local_locks.is_symlink()
    assert local_locks.resolve() == shared_locks.resolve()


def test_prepare_shared_runtime_files_recreates_worktree_local_data_dir_for_private_runtime_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_data = repo_root / "data"
    repo_data.mkdir(parents=True)
    shared_board = repo_data / "dev-tasks.json"
    shared_board.write_text('{"board":"shared"}\n', encoding="utf-8")
    shared_locks = repo_data / "locks"
    shared_locks.mkdir()

    worktree_dir = repo_root / ".worktrees" / "M175"

    prepare_shared_runtime_files(repo_root=repo_root, worktree_dir=worktree_dir)

    worktree_data = worktree_dir / "data"
    assert worktree_data.is_dir()
    assert not worktree_data.is_symlink()
    assert (worktree_data / "dev-tasks.json").is_symlink()
    assert (worktree_data / "dev-tasks.json").resolve() == shared_board.resolve()
    assert (worktree_data / "locks").is_symlink()
    assert (worktree_data / "locks").resolve() == shared_locks.resolve()
