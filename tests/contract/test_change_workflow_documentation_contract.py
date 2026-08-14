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


def test_strict_flow_routes_small_closures_before_worker_dispatch() -> None:
    workflow = _read("docs/development/change-workflow.md")
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")

    for classification in ("artifact-only", "bounded closure", "substantive"):
        assert classification in orchestrator
        assert classification in worker
    assert "不派 worker、不建 milestone/process docs" in orchestrator
    assert "不派 implementation worker" in orchestrator
    assert "ROUTE_BACK: artifact-only" in worker
    assert "ROUTE_BACK: bounded-closure" in worker
    assert "不改变用户可观察/稳定产品行为" in workflow
    assert "生产高风险边界时才是 bounded closure" in workflow
    assert "不能证明前两类时按 substantive" in workflow


def test_strict_worker_process_records_are_optional() -> None:
    workflow = _read("docs/development/change-workflow.md")
    storage = _read("docs/changes/README.md")
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    verifier = _read(".claude/skills/change-verifier/SKILL.md")
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")

    assert "roadpoint 数量、plan commit、逐步骤 push 或过程文档" in workflow
    assert "默认不创建 `tasks.md` / `progress.md`" in worker
    assert "缺少 `tasks.md` / `progress.md` 本身不是问题" in orchestrator
    assert "不再作为固定产物" in storage
    assert "缺少文件本身不是 finding" in verifier
    assert len(worker.splitlines()) <= 250


def test_worker_creator_owns_milestone_worktree_and_integration() -> None:
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")

    assert "worker 作为 creator-owner 创建、核对、集成并清理" in orchestrator
    assert "orchestrator 只提供精确的 milestone worktree/branch" in orchestrator
    assert "worker 是自己 milestone worktree/branch 的 creator-owner" in worker
    assert "unit_worktree_dir:" in worker
    assert "unit_branch:" in worker
    assert "删除自己创建的 milestone worktree/branch" in worker


def test_parallel_workers_share_one_unit_integration_lock() -> None:
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")
    integration = _read(
        ".claude/skills/change-impl-worker/references/worktree-integration.md"
    )

    assert "共享锁协议" in worker
    assert "--git-common-dir" in integration
    assert "nano-unit-locks/<unit_id>.lock" in integration
    assert "原子 `mkdir`" in integration
    assert "不得删除或接管" in integration
    assert "若已\n  前移" in integration
    assert "释放锁" in integration


def test_worker_done_reports_test_strategy_not_only_commands() -> None:
    orchestrator = _read(".claude/skills/change-orchestrator/SKILL.md")
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")

    for field in (
        "risk_and_seam",
        "existing_coverage",
        "disposition",
        "locator",
        "rationale",
        "lowest_layer_and_owner",
        "tested_head",
    ):
        assert field in worker
    assert "`test_strategy`" in orchestrator


def test_worker_reuses_valid_results_and_narrows_debugging_trigger() -> None:
    worker = _read(".claude/skills/change-impl-worker/SKILL.md")

    assert "三者未变时可以复用" in worker
    assert "不机械重复同一命令" in _read(".claude/skills/change-orchestrator/SKILL.md")
    assert "预期 TDD 红测" in worker
    assert "根因仍不明确" in worker
    assert "不要把所有非零退出都升级成完整调试流程" in worker
