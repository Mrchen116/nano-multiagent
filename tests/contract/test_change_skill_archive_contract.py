"""Archive-aware change workflow contracts."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_orchestrator_uses_resolved_unit_path_after_startup() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")
    operational_workflow = skill.split("## §2 启动序列", maxsplit=1)[1]

    assert "docs/changes/<unit_dir>" not in operational_workflow
    assert "$unit_worktree/$unit_path/M<next>-fix-<short-desc>/.gitkeep" in (
        operational_workflow
    )


def test_archive_aware_roles_reject_ambiguous_unit_paths() -> None:
    role_paths = (
        ".claude/skills/change-impl-worker/SKILL.md",
        ".claude/skills/change-reviewer/SKILL.md",
        ".claude/skills/change-verifier/SKILL.md",
    )

    for role_path in role_paths:
        skill = _read(role_path)
        assert "2>/dev/null | head -1" not in skill
        assert "unit path is ambiguous" in skill


def test_pr_templates_use_stable_absolute_blob_links() -> None:
    template = _read(
        ".claude/skills/change-orchestrator/references/pr-body-templates.md"
    )

    assert "](docs/changes/" not in template
    assert template.count("/blob/<pr_head_sha>/docs/changes/archive/") == 5


def test_archived_unit_with_open_pr_can_resume_orchestration() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")

    assert "resume_mode=post-pr" in skill
    assert "### §2.5 Post-PR resume" in skill
    assert skill.index("pr_candidates=$(gh pr list") < skill.index(
        'unit_matches=$(cd "$search_root" && find'
    )
    assert "scripts/prepare_unit_worktree.py" in skill


def test_design_revision_can_use_an_archived_unit_path() -> None:
    skill = _read(".claude/skills/change-design-author/SKILL.md")
    operational_workflow = skill.split("## §1 启动", maxsplit=1)[1]

    assert "revision_mode: post-pr" in skill
    assert "docs/changes/<unit_dir>" not in operational_workflow
    assert "unit path is ambiguous" in skill
    assert "current_branch=$(git branch --show-current)" in skill
    assert "state,headRefName,headRefOid,headRepository" in skill
    assert "current_repo=$(gh repo view --json nameWithOwner" in skill
    assert '"$pr_head_repo" != "$current_repo"' in skill
    assert "--validate-only" in skill


def test_post_pr_design_milestones_reenter_implementation_loop() -> None:
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    design_author = _read(".claude/skills/change-design-author/SKILL.md")
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")

    pending_call = orchestrator.index("pending_post_pr_milestones.py")
    feedback_call = orchestrator.index("address_pr_feedback_or_ci()")
    assert pending_call < feedback_call
    assert "milestones = pending_post_pr_milestones()" in orchestrator
    assert 'if resume_mode == "post-pr" and not milestones' in orchestrator
    assert "full_selection()" in orchestrator
    assert "update_existing_pr_watch_ci_exit()" in orchestrator
    assert "Added milestones:" in design_author
    assert "touch <unit_path>/M1-<title>/.gitkeep" in design_author
    assert 'rm -f "<unit_path>/<milestone_dir>/.gitkeep"' in worker
