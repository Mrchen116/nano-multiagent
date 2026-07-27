"""Contracts for the unit-scoped design-review lifecycle."""

import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_design_author_reuses_one_reviewer_and_does_not_choose_mode() -> None:
    skill = _read(".claude/skills/change-design-author/SKILL.md")
    review_loop = skill.split(
        "## §6 独立设计审查闭环(门禁 2 必做)", maxsplit=1
    )[1].split("## §7 完成信号", maxsplit=1)[0]

    assert "一个 unit 的整个 Gate 2 闭环只创建**一个** reviewer" in review_loop
    assert "R2 及以后不再创建 reviewer" in review_loop
    assert "唤醒 §6.1 的同一 reviewer" in review_loop
    assert "不传 `review_mode`" in review_loop
    assert "由 reviewer 核实际 delta 后自主选择" in review_loop
    assert "每轮启动全新独立 reviewer" not in review_loop
    assert "不得复用上一轮 reviewer" not in review_loop
    assert "固定路径只保留最新完整报告" not in review_loop


def test_design_reviewer_owns_modes_and_appends_auditable_rounds() -> None:
    skill = _read(".claude/skills/change-design-reviewer/SKILL.md")

    for mode in ("`closure`", "`delta`", "`full`"):
        assert mode in skill

    assert "author 只提供 changed artifacts" in skill
    assert "不应指定 `review_mode`" in skill
    assert "`rechecked`" in skill
    assert "`retained`" in skill
    assert "reviewed_artifact_manifest" in skill
    assert "started_at" in skill
    assert "completed_at" in skill
    assert "duration" in skill
    assert "prior_history_sha256" in skill
    assert "prior_history_bytes" in skill
    assert "R<round>-C<n>" in skill
    assert "Author Resolutions" in skill
    assert "每轮只在末尾追加一个完整 `## Round N`" in skill
    assert "禁止覆盖、重排、压缩或改写旧 Round" in skill


def test_orchestrator_consumes_latest_design_review_gate() -> None:
    skill = _read(".claude/skills/change-orchestrator/SKILL.md")
    startup_gate = skill.split(
        "### §2.1 模式判定 + 门禁 2 检查", maxsplit=1
    )[1].split("### §2.2 Sync Gate", maxsplit=1)[0]

    assert "Approved — 0 CRITICAL / 0 WARNING" in startup_gate
    assert "历史问题闭环 + `Author Resolutions`" in startup_gate
    assert "reviewed_artifact_manifest" in startup_gate
    assert "路径集合和 hash 必须同时相等" in startup_gate
    assert "首次派 worker 与 design 修订后重启 orchestrator 的共同门" in startup_gate
    assert "优先唤醒报告里的同一 design reviewer target" in startup_gate


def test_workflow_entrypoints_share_the_round_contract() -> None:
    changes_readme = _read("docs/changes/readme.md")
    agents = _read("AGENTS.md")

    for document in (changes_readme, agents):
        assert "同一" in document
        assert "`closure` / `delta` / `full`" in document
        assert "0 CRITICAL / 0 WARNING" in document
        assert "manifest" in document

    assert "按 `## Round N` 保留全部轮次" in changes_readme
    assert "每轮时间、问题与 Author Resolutions" in changes_readme
    assert "按 Round 追加" in agents


def test_feat_485_canary_reused_reviewer_and_preserved_round_one() -> None:
    report_path = (
        REPO_ROOT
        / "docs/changes/feat-485-design-review-round-lifecycle/design-review.md"
    )
    report_bytes = report_path.read_bytes()
    report = report_bytes.decode("utf-8")
    round_one, round_two = report.split("## Round 2", maxsplit=1)

    assert "## Round 1" in round_one
    assert "reviewer: `/root/design_reviewer_485`" in round_one
    assert "[R1-C1][CRITICAL]" in round_one
    assert "### Author Resolutions" in round_one

    assert "reviewer: `/root/design_reviewer_485`" in round_two
    assert "prior_history_sha256" in round_two
    assert "prior_history_bytes: `25616`" in round_two
    assert "Approved — 0 CRITICAL / 0 WARNING" in round_two
    assert hashlib.sha256(report_bytes[:25616]).hexdigest() == (
        "871abee334564e350153b7c5d645a781942d8c26cade09387653302f1fc5c600"
    )
