"""Contract tests for the documented change-* lifecycle invariants."""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).parent.parent.parent


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _table_rows(markdown: str) -> dict[str, tuple[str, ...]]:
    rows: dict[str, tuple[str, ...]] = {}
    for line in markdown.splitlines():
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip("|").split("|"))
        if cells and cells[0] not in {"Unit 类型", "---"}:
            rows[cells[0]] = cells[1:]
    return rows


def test_spec_review_remains_optional() -> None:
    workflow = _read("docs/development/change-workflow.md")
    storage = _read("docs/changes/README.md")

    assert "`change-spec-reviewer` 是可选的独立复核" in workflow
    assert "它不是 Full 流程的默认强制门禁" in workflow
    assert "`spec-review.md` 不是 Full 的必备文件" in storage


def test_gate_two_reuses_one_reviewer_until_clean_approval() -> None:
    workflow = _read("docs/development/change-workflow.md")
    author_skill = _read(".claude/skills/change-design-author/SKILL.md")

    assert "一个 unit 的 Gate 2 使用同一个独立 `change-design-reviewer`" in workflow
    assert "后续轮次唤醒同一 reviewer" in workflow
    assert "最后一个完整 Round 为 `Approved`" in workflow
    assert "`0 CRITICAL / 0 WARNING`" in workflow
    assert "一个 unit 的整个 Gate 2 闭环只创建**一个** reviewer" in author_skill
    assert "由 reviewer 根据实际改动选择 `closure`、`delta` 或 `full`" in workflow


def test_selected_validation_gate_matrix_does_not_drift() -> None:
    workflow = _read("docs/development/change-workflow.md")
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    simple_orchestrator = _read(".claude/skills/change-orchestrator-simple/SKILL.md")
    rows = _table_rows(workflow)

    assert rows["Full，存在用户可观察旅程"] == ("必须", "必须", "必须")
    assert rows["Full，零用户面"] == ("必须", "跳过", "必须")
    assert rows["Bugfix lite"] == ("跳过", "跳过", "必须")
    assert (
        "full 普通 unit → 三道闸全跑;零用户面 unit → verifier + code review;"
        "lite → 只跑 code review"
    ) in orchestrator
    assert "用户点名 `$change-orchestrator-simple` 时使用" in simple_orchestrator
    assert (
        "零用户面：执行 `$change-verifier` 和 `$change-code-review`"
        in simple_orchestrator
    )
    assert "不派产品 reviewer" in simple_orchestrator
