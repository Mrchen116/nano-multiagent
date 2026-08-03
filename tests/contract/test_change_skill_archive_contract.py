"""Archive-aware change workflow contracts."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_orchestrator_resolves_one_unit_dir_for_fix_and_archive() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")

    assert "按 `unit_id` 唯一解析真实\n`unit_dir`" in skill
    assert "`M<N>-fix-*`" in skill
    assert "用 `git mv` 把完整 unit 目录从 active 移入" in skill


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

    assert (
        "archive unit + 匹配的开放 `unit/<unit_id>` PR：只进入“开放 PR 小修”" in skill
    )
    assert "## 开放 PR 小修" in skill
    assert "恢复 exact PR head 的 clean unit worktree" in skill
    assert (
        "只自动处理不改变需求/design、不新增设计型 milestone 的 self-contained fix"
        in skill
    )
    assert "需要改变 design、范围或新增设计型 milestone 时停止" in skill


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
    assert "目录只含 `.gitkeep`" in orchestrator
    assert "用 `git mv` 把完整 unit 目录从 active 移入" in orchestrator
