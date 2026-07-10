"""Tests for durable post-PR revision lifecycle state."""

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
REVISION_STATE = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "change-orchestrator"
    / "scripts"
    / "post_pr_revision_state.py"
)


def _run(unit: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REVISION_STATE),
            command,
            "--unit-doc-root",
            str(unit),
            "--unit-id",
            "feat-1",
            *args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _head(unit: Path) -> str:
    return _git(unit, "rev-parse", "HEAD")


def _commit_all(unit: Path, message: str) -> str:
    _git(unit, "add", "-A")
    _git(unit, "commit", "-qm", message)
    return _head(unit)


def _prepare_unit(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-q", "-b", "unit/feat-1", str(repository)],
        check=True,
    )
    _git(repository, "config", "user.email", "test@example.com")
    _git(repository, "config", "user.name", "Test")
    unit = repository / "docs" / "changes" / "archive" / "feat-1-demo"
    completed = unit / "M1-completed"
    new_work = unit / "M2-new-work"
    completed.mkdir(parents=True)
    new_work.mkdir()
    (completed / "tasks.md").write_text("| R1 | existing | DONE |\n", encoding="utf-8")
    (completed / "progress.md").write_text("evidence\n", encoding="utf-8")
    (new_work / ".gitkeep").touch()
    (unit / "design.md").write_text(
        "| Milestone | Title |\n"
        "|---|---|\n"
        "| feat-1-M1 | completed |\n"
        "| feat-1-M2 | new work |\n",
        encoding="utf-8",
    )
    _commit_all(unit, "revision design")
    return unit


def _create(unit: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        unit,
        "create",
        "--revision-base-head",
        _head(unit),
        "--milestone",
        "M2-new-work",
    )


def _inspect(unit: Path) -> dict[str, object]:
    result = _run(unit, "inspect")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _mark(
    unit: Path, milestone: str, status: str, head: str
) -> subprocess.CompletedProcess[str]:
    return _run(
        unit,
        "mark",
        "--milestone",
        milestone,
        "--status",
        status,
        "--head",
        head,
    )


def test_revision_lifecycle_persists_each_resume_action(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")

    initial = _inspect(unit)
    assert initial["action"] == "implement"
    assert initial["statuses"] == {"M2-new-work": "unstarted"}

    dispatch_head = _head(unit)
    marked_in_progress = _mark(unit, "M2-new-work", "in_progress", dispatch_head)
    assert marked_in_progress.returncode == 0, marked_in_progress.stderr
    _commit_all(unit, "mark M2 in progress")
    in_progress = _inspect(unit)
    assert in_progress["action"] == "implement"
    assert in_progress["statuses"] == {"M2-new-work": "in_progress"}

    milestone = unit / "M2-new-work"
    (milestone / ".gitkeep").unlink()
    (milestone / "tasks.md").write_text(
        "| R1 | implementation | DOING |\n", encoding="utf-8"
    )
    (milestone / "progress.md").write_text("in progress\n", encoding="utf-8")
    (milestone / "tasks.md").write_text(
        "| R1 | implementation | DONE |\n", encoding="utf-8"
    )
    worker_head = _commit_all(unit, "implement M2")
    marked_implemented = _mark(unit, "M2-new-work", "implemented", worker_head)
    assert marked_implemented.returncode == 0, marked_implemented.stderr
    implemented_head = _commit_all(unit, "mark M2 implemented")
    awaiting_gates = _inspect(unit)
    assert awaiting_gates["action"] == "ready_for_full_gates"

    transition = _run(
        unit,
        "transition",
        "--phase",
        "full_gates_pending",
        "--head",
        implemented_head,
    )
    assert transition.returncode == 0, transition.stderr
    _commit_all(unit, "mark full gates pending")
    assert _inspect(unit)["action"] == "full_gates"

    (unit / "acceptance.md").write_text("full gates pass\n", encoding="utf-8")
    validated_head = _commit_all(unit, "record full gate reports")

    validated = _run(
        unit,
        "transition",
        "--phase",
        "validated",
        "--head",
        validated_head,
    )
    assert validated.returncode == 0, validated.stderr
    _commit_all(unit, "mark revision validated")
    assert _inspect(unit)["action"] == "validated"


def test_worker_completion_before_gate_transition_never_becomes_feedback(
    tmp_path: Path,
) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")
    dispatch_head = _head(unit)
    assert _mark(unit, "M2-new-work", "in_progress", dispatch_head).returncode == 0
    _commit_all(unit, "mark M2 in progress")
    milestone = unit / "M2-new-work"
    (milestone / ".gitkeep").unlink()
    (milestone / "tasks.md").write_text(
        "| R1 | implementation | DONE |\n", encoding="utf-8"
    )
    (milestone / "progress.md").write_text("done\n", encoding="utf-8")
    _commit_all(unit, "worker completed before restart")

    resumed = _inspect(unit)

    assert resumed["action"] == "implement"
    assert resumed["phase"] == "implementation_pending"
    assert resumed["statuses"] == {"M2-new-work": "in_progress"}


def test_signed_off_worker_before_gate_transition_requires_full_gates(
    tmp_path: Path,
) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")
    dispatch_head = _head(unit)
    assert _mark(unit, "M2-new-work", "in_progress", dispatch_head).returncode == 0
    _commit_all(unit, "mark M2 in progress")
    milestone = unit / "M2-new-work"
    (milestone / ".gitkeep").unlink()
    (milestone / "tasks.md").write_text(
        "| R1 | implementation | DONE |\n", encoding="utf-8"
    )
    (milestone / "progress.md").write_text("done\n", encoding="utf-8")
    worker_head = _commit_all(unit, "worker completed")
    assert _mark(unit, "M2-new-work", "implemented", worker_head).returncode == 0
    _commit_all(unit, "mark M2 implemented")

    resumed = _inspect(unit)

    assert resumed["action"] == "ready_for_full_gates"
    assert resumed["statuses"] == {"M2-new-work": "implemented"}


def test_absent_revision_state_uses_feedback_path(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)

    assert _inspect(unit) == {"phase": "none", "action": "feedback", "milestones": []}


def test_post_pr_fix_milestone_reopens_validated_lifecycle(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")
    dispatch_head = _head(unit)
    assert _mark(unit, "M2-new-work", "in_progress", dispatch_head).returncode == 0
    _commit_all(unit, "mark M2 in progress")
    milestone = unit / "M2-new-work"
    (milestone / ".gitkeep").unlink()
    (milestone / "tasks.md").write_text("| R1 | work | DONE |\n", encoding="utf-8")
    (milestone / "progress.md").write_text("done\n", encoding="utf-8")
    worker_head = _commit_all(unit, "implement revision")
    assert _mark(unit, "M2-new-work", "implemented", worker_head).returncode == 0
    implemented_head = _commit_all(unit, "mark M2 implemented")
    assert (
        _run(
            unit,
            "transition",
            "--phase",
            "full_gates_pending",
            "--head",
            implemented_head,
        ).returncode
        == 0
    )
    _commit_all(unit, "mark full gates pending")
    (unit / "verification.md").write_text("pass\n", encoding="utf-8")
    validated_head = _commit_all(unit, "full gate reports")
    assert (
        _run(
            unit,
            "transition",
            "--phase",
            "validated",
            "--head",
            validated_head,
        ).returncode
        == 0
    )
    _commit_all(unit, "mark validated")
    fix = unit / "M3-fix"
    fix.mkdir()
    (fix / ".gitkeep").touch()
    with (unit / "design.md").open("a", encoding="utf-8") as handle:
        handle.write("| feat-1-M3 | post-PR fix |\n")

    added = _run(
        unit,
        "add",
        "--revision-base-head",
        _head(unit),
        "--milestone",
        "M3-fix",
    )

    assert added.returncode == 0, added.stderr
    resumed = _inspect(unit)
    assert resumed["phase"] == "implementation_pending"
    assert resumed["milestones"] == ["M3-fix"]
    assert resumed["statuses"] == {
        "M2-new-work": "implemented",
        "M3-fix": "unstarted",
    }


def test_state_and_design_mismatch_fails_closed(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")
    (unit / "M2-new-work").rename(unit / "M3-wrong")

    result = _run(unit, "inspect")

    assert result.returncode != 0
    assert "design/directory milestone mismatch" in result.stderr


def test_untracked_empty_milestone_skeleton_fails_closed(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)
    (unit / "M2-new-work" / ".gitkeep").unlink()

    result = _create(unit)

    assert result.returncode != 0
    assert "milestone is not an empty tracked skeleton" in result.stderr


def test_state_transition_rejects_a_head_other_than_current_checkout(
    tmp_path: Path,
) -> None:
    unit = _prepare_unit(tmp_path)

    result = _run(
        unit,
        "create",
        "--revision-base-head",
        "a" * 40,
        "--milestone",
        "M2-new-work",
    )

    assert result.returncode != 0
    assert "does not match worktree HEAD" in result.stderr


def test_milestone_cannot_skip_in_progress_state(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")
    milestone = unit / "M2-new-work"
    (milestone / ".gitkeep").unlink()
    (milestone / "tasks.md").write_text("done\n", encoding="utf-8")
    (milestone / "progress.md").write_text("done\n", encoding="utf-8")
    worker_head = _commit_all(unit, "unexpected worker output")

    result = _mark(unit, "M2-new-work", "implemented", worker_head)

    assert result.returncode != 0
    assert "from unstarted to implemented" in result.stderr


def test_validated_state_rejects_later_unvalidated_commit(tmp_path: Path) -> None:
    unit = _prepare_unit(tmp_path)
    assert _create(unit).returncode == 0
    _commit_all(unit, "persist revision state")
    dispatch_head = _head(unit)
    assert _mark(unit, "M2-new-work", "in_progress", dispatch_head).returncode == 0
    _commit_all(unit, "mark M2 in progress")
    milestone = unit / "M2-new-work"
    (milestone / ".gitkeep").unlink()
    (milestone / "tasks.md").write_text("| R1 | work | DONE |\n", encoding="utf-8")
    (milestone / "progress.md").write_text("done\n", encoding="utf-8")
    worker_head = _commit_all(unit, "implement revision")
    assert _mark(unit, "M2-new-work", "implemented", worker_head).returncode == 0
    implemented_head = _commit_all(unit, "mark M2 implemented")
    assert (
        _run(
            unit,
            "transition",
            "--phase",
            "full_gates_pending",
            "--head",
            implemented_head,
        ).returncode
        == 0
    )
    validated_head = _commit_all(unit, "mark full gates pending")
    assert (
        _run(
            unit,
            "transition",
            "--phase",
            "validated",
            "--head",
            validated_head,
        ).returncode
        == 0
    )
    _commit_all(unit, "mark validated")
    (unit / "unvalidated-change.md").write_text("drift\n", encoding="utf-8")
    _commit_all(unit, "unvalidated change")

    result = _run(unit, "inspect")

    assert result.returncode != 0
    assert "validated state does not cover the current HEAD" in result.stderr
