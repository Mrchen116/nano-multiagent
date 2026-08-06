"""Contracts for change-unit archive and delivery behavior."""

import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_pr_templates_use_stable_absolute_blob_links() -> None:
    template = _read(
        ".claude/skills/change-orchestrator/references/pr-body-templates.md"
    )

    link_targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", template)
    change_links = [target for target in link_targets if "docs/changes/" in target]

    assert change_links
    assert all(
        target.startswith(
            "<repo_url>/blob/<pr_head_sha>/docs/changes/archive/<unit_dir>/"
        )
        for target in change_links
    )


def _run_archive_check(
    repo_root: Path, head_ref: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/check_change_unit_archived.py"),
            "--head-ref",
            head_ref,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _create_unit(repo_root: Path, scope: str, unit_dir: str) -> None:
    path = repo_root / "docs/changes"
    if scope != "active":
        path /= scope
    (path / unit_dir).mkdir(parents=True)


def test_non_unit_branch_skips_archive_check(tmp_path: Path) -> None:
    result = _run_archive_check(tmp_path, "codex/docs-cleanup")

    assert result.returncode == 0
    assert "Skipping" in result.stdout


def test_unit_branch_passes_when_unique_unit_is_archived(tmp_path: Path) -> None:
    _create_unit(tmp_path, "archive", "feat-501-cross-channel-session-controls")

    result = _run_archive_check(tmp_path, "unit/feat-501")

    assert result.returncode == 0
    assert "archived" in result.stdout


@pytest.mark.parametrize("scope", ["active", "retired"])
def test_unit_branch_fails_when_unit_is_not_archived(
    tmp_path: Path, scope: str
) -> None:
    _create_unit(tmp_path, scope, "feat-501-cross-channel-session-controls")

    result = _run_archive_check(tmp_path, "unit/feat-501")

    assert result.returncode == 1
    assert scope in result.stderr
    assert "docs/changes/archive/" in result.stderr


def test_unit_branch_fails_when_unit_is_missing(tmp_path: Path) -> None:
    result = _run_archive_check(tmp_path, "unit/feat-501")

    assert result.returncode == 1
    assert "No change unit found" in result.stderr


def test_unit_branch_fails_when_unit_is_duplicated(tmp_path: Path) -> None:
    unit_dir = "feat-501-cross-channel-session-controls"
    _create_unit(tmp_path, "active", unit_dir)
    _create_unit(tmp_path, "archive", unit_dir)

    result = _run_archive_check(tmp_path, "unit/feat-501")

    assert result.returncode == 1
    assert "multiple locations" in result.stderr
    assert f"docs/changes/{unit_dir}" in result.stderr
    assert f"docs/changes/archive/{unit_dir}" in result.stderr


def test_unit_branch_with_suffix_extracts_unit_id(tmp_path: Path) -> None:
    _create_unit(tmp_path, "archive", "feat-503-feishu-e2e-runtime")

    result = _run_archive_check(tmp_path, "unit/feat-503-feishu-e2e")

    assert result.returncode == 0


def test_ci_runs_archive_check_for_pull_requests() -> None:
    workflow = _read(".github/workflows/ci.yml")

    assert "python scripts/check_change_unit_archived.py" in workflow
    assert "github.head_ref" in workflow


def test_simple_orchestrator_delivers_ready_pull_request() -> None:
    skill = _read(".claude/skills/change-orchestrator-simple/SKILL.md")

    assert "Ready for review" in skill
    assert "不得使用 `--draft`" in skill
    assert "`gh pr ready`" in skill
