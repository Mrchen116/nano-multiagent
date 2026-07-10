#!/usr/bin/env python3
"""Create or safely restore the worktree for a unit integration branch."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


class WorktreeError(RuntimeError):
    """Raised when worktree restoration would mutate an unexpected checkout."""


def git(
    repository: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run Git in a repository and retain output for validation errors."""
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise WorktreeError(message or f"git {' '.join(args)} failed")
    return result


def git_output(repository: Path, *args: str) -> str:
    """Return stripped stdout from a successful Git command."""
    return git(repository, *args).stdout.strip()


def git_common_dir(repository: Path) -> Path:
    """Resolve the common Git directory shared by linked worktrees."""
    return Path(
        git_output(
            repository,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        )
    ).resolve()


def validate_existing_worktree(
    repo_root: Path,
    worktree_dir: Path,
    expected_branch: str,
) -> None:
    """Fail before mutation when a path is not the expected linked worktree."""
    if not worktree_dir.exists():
        return
    if not worktree_dir.is_dir():
        raise WorktreeError(f"worktree path is not a directory: {worktree_dir}")

    top_level = Path(git_output(worktree_dir, "rev-parse", "--show-toplevel")).resolve()
    if top_level != worktree_dir.resolve():
        raise WorktreeError(
            f"worktree path belongs to a different checkout root: {top_level}"
        )
    if git_common_dir(worktree_dir) != git_common_dir(repo_root):
        raise WorktreeError("worktree path belongs to a different Git repository")

    actual_branch = git_output(worktree_dir, "branch", "--show-current")
    if actual_branch != expected_branch:
        raise WorktreeError(
            f"worktree path belongs to branch {actual_branch or '<detached>'}; "
            f"expected {expected_branch}"
        )


def branch_worktree(repo_root: Path, branch: str) -> Path | None:
    """Return the path already holding a branch, if any."""
    current_path: Path | None = None
    for line in git_output(repo_root, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}":
            return current_path
    return None


def remote_branch_exists(repo_root: Path, remote: str, branch: str) -> bool:
    """Distinguish an absent remote branch from transport or auth failures."""
    result = git(
        repo_root,
        "ls-remote",
        "--exit-code",
        "--heads",
        remote,
        f"refs/heads/{branch}",
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 2:
        return False
    message = result.stderr.strip() or result.stdout.strip()
    raise WorktreeError(message or f"cannot inspect {remote}/{branch}")


def prepare_worktree(
    repo_root: Path,
    unit_id: str,
    worktree_dir: Path,
    expected_head: str | None,
    create_from: str,
    remote: str,
) -> None:
    """Create or restore one unit worktree without touching an unrelated branch."""
    repo_root = repo_root.resolve()
    worktree_dir = worktree_dir.resolve()
    branch = f"unit/{unit_id}"
    remote_ref = f"refs/remotes/{remote}/{branch}"

    validate_existing_worktree(repo_root, worktree_dir, branch)
    remote_exists = remote_branch_exists(repo_root, remote, branch)
    if remote_exists:
        git(
            repo_root,
            "fetch",
            remote,
            f"+refs/heads/{branch}:{remote_ref}",
        )
    local_exists = (
        git(
            repo_root, "show-ref", "--verify", f"refs/heads/{branch}", check=False
        ).returncode
        == 0
    )

    if expected_head is not None and not remote_exists:
        raise WorktreeError(f"open PR branch is missing from {remote}: {branch}")
    remote_head = (
        git_output(repo_root, "rev-parse", remote_ref) if remote_exists else None
    )
    if expected_head is not None and remote_head != expected_head:
        raise WorktreeError(
            f"PR head {expected_head} does not match {remote}/{branch} {remote_head}"
        )
    target_head = expected_head or remote_head

    if local_exists and target_head is not None:
        local_head = git_output(repo_root, "rev-parse", f"refs/heads/{branch}")
        if local_head != target_head:
            ancestor = git(
                repo_root,
                "merge-base",
                "--is-ancestor",
                local_head,
                target_head,
                check=False,
            )
            if ancestor.returncode != 0:
                raise WorktreeError(
                    f"local {branch} cannot fast-forward to {target_head}"
                )

    if not worktree_dir.exists():
        occupied_path = branch_worktree(repo_root, branch) if local_exists else None
        if occupied_path is not None:
            raise WorktreeError(
                f"branch {branch} is already checked out at {occupied_path}"
            )
        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        if local_exists:
            git(repo_root, "worktree", "add", str(worktree_dir), branch)
        elif remote_exists:
            git(repo_root, "branch", "--track", branch, f"{remote}/{branch}")
            git(repo_root, "worktree", "add", str(worktree_dir), branch)
        else:
            git(
                repo_root,
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree_dir),
                create_from,
            )

    if remote_exists:
        assert target_head is not None
        current_head = git_output(worktree_dir, "rev-parse", "HEAD")
        if current_head != target_head:
            ancestor = git(
                worktree_dir,
                "merge-base",
                "--is-ancestor",
                current_head,
                target_head,
                check=False,
            )
            if ancestor.returncode != 0:
                raise WorktreeError(
                    f"local {branch} cannot fast-forward to {target_head}"
                )
            git(worktree_dir, "merge", "--ff-only", target_head)
    else:
        git(worktree_dir, "push", "-u", remote, branch)

    validate_existing_worktree(repo_root, worktree_dir, branch)
    if expected_head is not None:
        actual_head = git_output(worktree_dir, "rev-parse", "HEAD")
        if actual_head != expected_head:
            raise WorktreeError(
                f"restored HEAD {actual_head} does not match PR head {expected_head}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--worktree-dir", type=Path, required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--create-from", default="main")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()

    try:
        prepare_worktree(
            args.repo_root,
            args.unit_id,
            args.worktree_dir,
            args.expected_head,
            args.create_from,
            args.remote,
        )
    except WorktreeError as error:
        parser.error(str(error))
    print(args.worktree_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
