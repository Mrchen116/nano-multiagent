"""Prepare shared runtime files for milestone worktrees.

Milestone worktrees under ``<repo_root>/.worktrees`` must not keep their own copy
of runtime coordination files. In particular, the dispatch board and merge locks
must resolve to the same repository-owned paths so multiple workers do not fork
scheduler state.
"""

from __future__ import annotations

from pathlib import Path
import shutil


_SHARED_RUNTIME_PATHS: tuple[tuple[str, bool], ...] = (
    ("data/dev-tasks.json", False),
    ("data/locks", True),
)


def prepare_shared_runtime_files(*, repo_root: Path, worktree_dir: Path) -> None:
    """Align worktree runtime files with the repository-owned shared copies.

    Args:
        repo_root: Canonical repository root that owns the shared runtime files.
        worktree_dir: Milestone worktree path that should consume the shared
            runtime files instead of private copies.

    Side Effects:
        Replaces worktree-local files/directories with symlinks pointing at the
        repository-owned runtime paths.

    Notes:
        The helper is intentionally idempotent so worktree reuse and repair can
        run the same hygiene step multiple times without mutating shared content.
    """

    resolved_repo_root = repo_root.expanduser().resolve()
    resolved_worktree_dir = worktree_dir.expanduser().resolve()
    for relative_path, target_is_directory in _SHARED_RUNTIME_PATHS:
        shared_path = resolved_repo_root / relative_path
        worktree_path = resolved_worktree_dir / relative_path
        _ensure_symlink(
            link_path=worktree_path,
            target_path=shared_path,
            target_is_directory=target_is_directory,
        )


def _ensure_symlink(*, link_path: Path, target_path: Path, target_is_directory: bool) -> None:
    """Replace ``link_path`` with a symlink to ``target_path`` when needed."""

    if link_path.is_symlink() and link_path.resolve() == target_path.resolve():
        return

    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_dir() and not link_path.is_symlink():
            shutil.rmtree(link_path)
        else:
            link_path.unlink()
    link_path.symlink_to(target_path, target_is_directory=target_is_directory)
