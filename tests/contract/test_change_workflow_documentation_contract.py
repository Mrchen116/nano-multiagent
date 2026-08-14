"""Contract tests for the documented change-* lifecycle invariants."""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).parent.parent.parent


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _table_cells(line: str) -> tuple[str, ...] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return tuple(cell.strip() for cell in stripped.strip("|").split("|"))


def _table_rows(
    markdown: str,
    columns: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    lines = markdown.splitlines()
    header_index = next(
        index for index, line in enumerate(lines) if _table_cells(line) == columns
    )
    rows: dict[str, tuple[str, ...]] = {}
    for line in lines[header_index + 2 :]:
        cells = _table_cells(line)
        if cells is None:
            break
        rows[cells[0]] = cells[1:]
    return rows


def test_spec_review_remains_optional() -> None:
    workflow = _read("docs/development/change-workflow.md")
    storage = _read("docs/changes/README.md")

    workflow_mentions = [
        line for line in workflow.splitlines() if "`change-spec-reviewer`" in line
    ]
    storage_mentions = [
        line for line in storage.splitlines() if "`spec-review.md`" in line
    ]
    assert any("可选" in line or "按需" in line for line in workflow_mentions)
    assert any("可选" in line or "按需" in line for line in storage_mentions)


def test_gate_two_reuses_one_reviewer_until_clean_approval() -> None:
    workflow = _read("docs/development/change-workflow.md")
    author_skill = _read(".claude/skills/change-design-author/SKILL.md")

    workflow_lines = workflow.splitlines()
    assert any(
        "Gate 2" in line and "同一个" in line and "`change-design-reviewer`" in line
        for line in workflow_lines
    )
    assert any("后续" in line and "同一 reviewer" in line for line in workflow_lines)
    assert any("`Approved`" in line for line in workflow_lines)
    assert any("CRITICAL" in line and "WARNING" in line for line in workflow_lines)
    assert any(
        "Gate 2" in line and "只创建" in line and "一个" in line
        for line in author_skill.splitlines()
    )


def test_selected_validation_gate_matrix_does_not_drift() -> None:
    workflow = _read("docs/development/change-workflow.md")
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    simple_orchestrator = _read(".claude/skills/change-orchestrator-simple/SKILL.md")
    workflow_rows = _table_rows(
        workflow,
        (
            "Unit 类型",
            "`change-verifier`",
            "`change-reviewer`",
            "`change-code-review`",
        ),
    )
    orchestrator_rows = _table_rows(
        orchestrator,
        ("Unit", "Product reviewer", "Verifier", "Code review"),
    )

    row_pairs = {
        "Full，存在用户可观察旅程": "Full，有用户可观察旅程",
        "Full，零用户面": "Full，零用户面",
        "Bugfix lite": "Bugfix lite",
    }
    for workflow_name, orchestrator_name in row_pairs.items():
        verifier, reviewer, code_review = workflow_rows[workflow_name]
        normalized = tuple(
            "full" if value == "必须" else "skipped"
            for value in (reviewer, verifier, code_review)
        )
        assert orchestrator_rows[orchestrator_name] == normalized
    assert "不派产品 reviewer" in simple_orchestrator
    assert "Bugfix lite：只执行 `$change-code-review`" in simple_orchestrator
    assert "不派 verifier 或产品 reviewer" in simple_orchestrator


def test_simplified_flow_supports_full_and_bugfix_lite() -> None:
    workflow = _read("docs/development/change-workflow.md")
    simple_orchestrator = _read(".claude/skills/change-orchestrator-simple/SKILL.md")

    assert "Bugfix lite 在两种方式下都保持唯一的 `M1-fix`" in workflow
    assert "Full 和 Bugfix lite 的门禁组合同时适用" in workflow
    assert "Full 或 Bugfix lite change unit" in simple_orchestrator
    assert "不因此强制创建 `tasks.md` 或 `progress.md`" in simple_orchestrator
