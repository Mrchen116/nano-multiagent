"""Archive-aware change workflow contracts."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_orchestrator_uses_resolved_unit_path_after_startup() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")
    operational_workflow = skill.split("## §2 启动序列", maxsplit=1)[1]

    assert "docs/changes/<unit_dir>" not in operational_workflow
    assert "`$unit_path/M<next>-fix-<short-desc>/`" in operational_workflow


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


def test_archived_unit_with_open_pr_only_resumes_self_contained_fixes() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")

    assert "resume_mode=post-pr" in skill
    assert "### §2.5 Post-PR 小修" in skill
    assert 'git worktree add "$unit_worktree" "unit/<unit-id>"' in skill
    assert "exact PR head, and clean worktree" in skill
    assert "不改 design、不新增 milestone" in skill
    assert "第二套 design/implementation 生命周期" in skill


def test_archive_workflow_has_no_transactional_recovery_helpers() -> None:
    scripts = REPO_ROOT / ".claude/skills/change-orchestrator/scripts"

    assert not (scripts / "prepare_unit_worktree.py").exists()
    assert not (scripts / "post_pr_revision_state.py").exists()


def test_design_skeletons_are_trackable_without_recovery_state() -> None:
    design_author = _read(".claude/skills/change-design-author/SKILL.md")
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")

    assert "M1-<title>/.gitkeep" in design_author
    assert 'rm -f "<unit_path>/<milestone_dir>/.gitkeep"' in worker
    assert "子目录仅含 `.gitkeep`" in orchestrator
    assert 'git -C "$unit_worktree" mv "$unit_path" "$archive_path"' in orchestrator
