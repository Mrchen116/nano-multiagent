"""Tests for the change-spec-author unit id allocator."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOCATOR = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "change-spec-author"
    / "scripts"
    / "next_unit_id.py"
)


def _allocate(
    changes_dir: Path,
    state_dir: Path | None = None,
    change_type: str = "feat",
) -> str:
    command = [
        sys.executable,
        str(ALLOCATOR),
        change_type,
        "--changes-dir",
        str(changes_dir),
    ]
    if state_dir is not None:
        command.extend(("--state-dir", str(state_dir)))
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_allocator_scans_active_and_archived_units(tmp_path: Path) -> None:
    changes_dir = tmp_path / "changes"
    (changes_dir / "feat-7-active").mkdir(parents=True)
    (changes_dir / "archive" / "bugfix-11-archived").mkdir(parents=True)
    (changes_dir / "archive" / "refactor-9-older").mkdir()

    assert _allocate(changes_dir, tmp_path / "state", "perf") == "perf-12"


def test_allocator_persists_reservations_before_unit_directory_exists(
    tmp_path: Path,
) -> None:
    changes_dir = tmp_path / "changes"
    changes_dir.mkdir()
    state_dir = tmp_path / "state"

    assert _allocate(changes_dir, state_dir, "feat") == "feat-1"
    assert _allocate(changes_dir, state_dir, "refactor") == "refactor-2"


def test_concurrent_allocations_are_unique(tmp_path: Path) -> None:
    changes_dir = tmp_path / "changes"
    (changes_dir / "archive" / "docs-12-existing").mkdir(parents=True)
    state_dir = tmp_path / "state"

    with ThreadPoolExecutor(max_workers=8) as executor:
        allocated = list(
            executor.map(
                lambda _: _allocate(changes_dir, state_dir),
                range(8),
            )
        )

    assert len(set(allocated)) == 8
    assert {int(unit_id.removeprefix("feat-")) for unit_id in allocated} == set(
        range(13, 21)
    )


def test_default_reservation_state_is_shared_by_git_worktrees(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Test"], check=True
    )
    changes_dir = repository / "docs" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / ".gitkeep").touch()
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "initial"], check=True
    )

    second_worktree = tmp_path / "second-worktree"
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "worktree",
            "add",
            "-qb",
            "second",
            str(second_worktree),
        ],
        check=True,
    )

    assert _allocate(changes_dir, change_type="feat") == "feat-1"
    assert (
        _allocate(second_worktree / "docs" / "changes", change_type="bugfix")
        == "bugfix-2"
    )
