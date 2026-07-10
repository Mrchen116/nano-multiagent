"""Tests for safe restoration of a change unit worktree."""

from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PREPARE_WORKTREE = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "change-orchestrator"
    / "scripts"
    / "prepare_unit_worktree.py"
)


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _prepare_remote(tmp_path: Path) -> tuple[Path, str]:
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)

    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "config", "user.name", "Test")
    active_unit = seed / "docs" / "changes" / "feat-1-demo"
    active_unit.mkdir(parents=True)
    (active_unit / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(seed, "add", ".")
    _git(seed, "commit", "-qm", "active unit")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-qu", "origin", "main")
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")

    _git(seed, "switch", "-qc", "unit/feat-1")
    archive_root = seed / "docs" / "changes" / "archive"
    archive_root.mkdir()
    active_unit.rename(archive_root / active_unit.name)
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "archive unit")
    unit_head = _git(seed, "rev-parse", "HEAD")
    _git(seed, "push", "-qu", "origin", "unit/feat-1")
    return remote, unit_head


def _clone(remote: Path, destination: Path) -> None:
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(destination)],
        check=True,
    )


def _run_prepare(
    repository: Path,
    worktree: Path,
    expected_head: str | None,
    *,
    validate_only: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(PREPARE_WORKTREE),
        "--repo-root",
        str(repository),
        "--unit-id",
        "feat-1",
        "--worktree-dir",
        str(worktree),
    ]
    if expected_head is not None:
        command.extend(("--expected-head", expected_head))
    if validate_only:
        command.append("--validate-only")
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )


def test_restore_uses_pr_branch_before_resolving_archived_unit(
    tmp_path: Path,
) -> None:
    remote, unit_head = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"

    result = _run_prepare(repository, unit_worktree, unit_head)

    assert result.returncode == 0, result.stderr
    assert _git(unit_worktree, "branch", "--show-current") == "unit/feat-1"
    assert _git(unit_worktree, "rev-parse", "HEAD") == unit_head
    assert (unit_worktree / "docs" / "changes" / "archive" / "feat-1-demo").is_dir()
    assert not (unit_worktree / "docs" / "changes" / "feat-1-demo").exists()


def test_existing_worktree_on_wrong_branch_fails_without_mutation(
    tmp_path: Path,
) -> None:
    remote, unit_head = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"
    _git(repository, "branch", "other")
    _git(repository, "worktree", "add", "-q", str(unit_worktree), "other")
    original_head = _git(unit_worktree, "rev-parse", "HEAD")

    result = _run_prepare(repository, unit_worktree, unit_head)

    assert result.returncode != 0
    assert "belongs to branch other" in result.stderr
    assert _git(unit_worktree, "branch", "--show-current") == "other"
    assert _git(unit_worktree, "rev-parse", "HEAD") == original_head


def test_validate_only_rejects_worktree_from_different_repository(
    tmp_path: Path,
) -> None:
    remote, _ = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)

    foreign = tmp_path / "foreign"
    subprocess.run(
        ["git", "init", "-q", "-b", "unit/feat-1", str(foreign)],
        check=True,
    )
    _git(foreign, "config", "user.email", "test@example.com")
    _git(foreign, "config", "user.name", "Test")
    (foreign / "README.md").write_text("foreign\n", encoding="utf-8")
    _git(foreign, "add", "README.md")
    _git(foreign, "commit", "-qm", "foreign")
    foreign_head = _git(foreign, "rev-parse", "HEAD")

    result = _run_prepare(
        repository,
        foreign,
        foreign_head,
        validate_only=True,
    )

    assert result.returncode != 0
    assert "different Git repository" in result.stderr


@pytest.mark.parametrize("change_kind", ("staged", "unstaged", "untracked"))
def test_existing_dirty_worktree_fails_before_recovery(
    tmp_path: Path,
    change_kind: str,
) -> None:
    remote, unit_head = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"
    assert _run_prepare(repository, unit_worktree, unit_head).returncode == 0

    tracked_file = (
        unit_worktree / "docs" / "changes" / "archive" / "feat-1-demo" / "spec.md"
    )
    if change_kind == "untracked":
        (unit_worktree / "local-drift.txt").write_text("drift\n", encoding="utf-8")
    else:
        tracked_file.write_text("# changed\n", encoding="utf-8")
        if change_kind == "staged":
            _git(unit_worktree, "add", str(tracked_file))

    result = _run_prepare(repository, unit_worktree, unit_head)

    assert result.returncode != 0
    assert "worktree has staged, unstaged, or untracked changes" in result.stderr
    assert _git(unit_worktree, "rev-parse", "HEAD") == unit_head


def test_pr_head_mismatch_fails_before_creating_worktree(tmp_path: Path) -> None:
    remote, _ = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"

    result = _run_prepare(repository, unit_worktree, "0" * 40)

    assert result.returncode != 0
    assert "does not match origin/unit/feat-1" in result.stderr
    assert not unit_worktree.exists()


def test_validate_only_rejects_stale_or_ahead_head(
    tmp_path: Path,
) -> None:
    remote, unit_head = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"
    assert _run_prepare(repository, unit_worktree, unit_head).returncode == 0

    seed = tmp_path / "seed"
    (seed / "after-review.txt").write_text("new head\n", encoding="utf-8")
    _git(seed, "add", "after-review.txt")
    _git(seed, "commit", "-qm", "advance pull request")
    new_pr_head = _git(seed, "rev-parse", "HEAD")
    _git(seed, "push", "-q", "origin", "unit/feat-1")

    stale = _run_prepare(
        repository,
        unit_worktree,
        new_pr_head,
        validate_only=True,
    )
    assert stale.returncode != 0
    assert "does not match PR head" in stale.stderr

    _git(unit_worktree, "config", "user.email", "test@example.com")
    _git(unit_worktree, "config", "user.name", "Test")
    (unit_worktree / "local-ahead.txt").write_text("ahead\n", encoding="utf-8")
    _git(unit_worktree, "add", "local-ahead.txt")
    _git(unit_worktree, "commit", "-qm", "local ahead")
    ahead = _run_prepare(
        repository,
        unit_worktree,
        unit_head,
        validate_only=True,
    )
    assert ahead.returncode != 0
    assert "does not match PR head" in ahead.stderr


def test_remote_inspection_failure_does_not_create_fresh_branch(
    tmp_path: Path,
) -> None:
    remote, _ = _prepare_remote(tmp_path)
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"
    _git(repository, "remote", "set-url", "origin", str(tmp_path / "missing.git"))

    result = _run_prepare(repository, unit_worktree, None)

    assert result.returncode != 0
    assert not unit_worktree.exists()
    local_branch = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "show-ref",
            "--verify",
            "refs/heads/unit/feat-1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert local_branch.returncode != 0


def test_fresh_unit_branch_is_created_from_main_and_pushed(tmp_path: Path) -> None:
    remote, _ = _prepare_remote(tmp_path)
    seed = tmp_path / "seed"
    _git(seed, "push", "-q", "origin", "--delete", "unit/feat-1")
    repository = tmp_path / "consumer"
    _clone(remote, repository)
    unit_worktree = repository / ".worktrees" / "unit-feat-1"
    main_head = _git(repository, "rev-parse", "main")

    result = _run_prepare(repository, unit_worktree, None)

    assert result.returncode == 0, result.stderr
    assert _git(unit_worktree, "branch", "--show-current") == "unit/feat-1"
    assert _git(unit_worktree, "rev-parse", "HEAD") == main_head
    assert _git(repository, "rev-parse", "origin/unit/feat-1") == main_head
