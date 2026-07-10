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


def test_archived_unit_with_open_pr_can_resume_orchestration() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")

    assert "resume_mode=post-pr" in skill
    assert "### §2.5 Post-PR resume" in skill
    assert 'git worktree add "$unit_worktree" "unit/<unit-id>"' in skill
