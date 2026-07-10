"""Tests for executable post-PR milestone state detection."""

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
PENDING_MILESTONES = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "change-orchestrator"
    / "scripts"
    / "pending_post_pr_milestones.py"
)


def _run(unit_doc_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PENDING_MILESTONES),
            "--unit-doc-root",
            str(unit_doc_root),
            "--unit-id",
            "feat-1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_only_unstarted_revision_milestones_are_pending(tmp_path: Path) -> None:
    unit = tmp_path / "docs" / "changes" / "archive" / "feat-1-demo"
    completed = unit / "M1-completed"
    pending = unit / "M2-new-work"
    later_pending = unit / "M10-follow-up"
    completed.mkdir(parents=True)
    pending.mkdir()
    later_pending.mkdir()
    (completed / "tasks.md").write_text("status: DONE\n", encoding="utf-8")
    (completed / "progress.md").write_text("evidence\n", encoding="utf-8")
    (pending / ".gitkeep").touch()
    (later_pending / ".gitkeep").touch()
    (unit / "specs").mkdir()
    (unit / "design.md").write_text(
        "| Milestone | Title |\n"
        "|---|---|\n"
        "| feat-1-M1 | completed |\n"
        "| feat-1-M2 | new work |\n"
        "| feat-1-M10 | follow-up |\n",
        encoding="utf-8",
    )

    result = _run(unit)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["M2-new-work", "M10-follow-up"]


def test_missing_unit_root_fails_closed(tmp_path: Path) -> None:
    result = _run(tmp_path / "missing")

    assert result.returncode != 0
    assert "unit document root does not exist" in result.stderr


def test_design_and_directory_mismatch_fails_closed(tmp_path: Path) -> None:
    unit = tmp_path / "feat-1-demo"
    (unit / "M1-existing").mkdir(parents=True)
    (unit / "design.md").write_text(
        "| feat-1-M1 | existing |\n| feat-1-M2 | missing |\n",
        encoding="utf-8",
    )

    result = _run(unit)

    assert result.returncode != 0
    assert "design/directory milestone mismatch" in result.stderr


def test_untracked_empty_milestone_skeleton_fails_closed(tmp_path: Path) -> None:
    unit = tmp_path / "feat-1-demo"
    (unit / "M1-untracked-empty").mkdir(parents=True)
    (unit / "design.md").write_text(
        "| feat-1-M1 | untracked empty |\n",
        encoding="utf-8",
    )

    result = _run(unit)

    assert result.returncode != 0
    assert "pending milestone is not Git-trackable" in result.stderr
