"""Unit tests for the repository documentation integrity checker."""

from __future__ import annotations

from pathlib import Path

from scripts import docs_check


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Path(relative)


def test_local_link_check_uses_markdown_ast_and_requires_tracked_target(
    tmp_path: Path,
) -> None:
    source = _write(
        tmp_path,
        "docs/development/guide.md",
        "```markdown\n[example only](missing.md)\n```\n\n"
        "[tracked](tracked.md)\n\n![tracked image](image.png)\n\n"
        "[untracked](untracked.md)\n",
    )
    tracked_target = _write(tmp_path, "docs/development/tracked.md", "# Tracked\n")
    tracked_image = _write(tmp_path, "docs/development/image.png", "image")
    _write(tmp_path, "docs/development/untracked.md", "# Local only\n")
    tracked = {source, tracked_target, tracked_image}

    problems = docs_check.check_local_links(tmp_path, tracked)

    assert [problem.code for problem in problems] == ["BROKEN_LINK"]
    assert "untracked.md" in problems[0].message
    assert "missing.md" not in problems[0].message


def test_reachability_follows_explicit_index_chain(tmp_path: Path) -> None:
    agents = _write(tmp_path, "AGENTS.md", "[map](docs/README.md)\n")
    docs_index = _write(
        tmp_path,
        "docs/README.md",
        "[development](development/README.md)\n",
    )
    development_index = _write(
        tmp_path,
        "docs/development/README.md",
        "[guide](guide.md)\n",
    )
    guide = _write(tmp_path, "docs/development/guide.md", "# Guide\n")
    orphan = _write(tmp_path, "docs/development/orphan.md", "# Orphan\n")
    tracked = {agents, docs_index, development_index, guide, orphan}

    reachable = docs_check.reachable_files(tmp_path, tracked)

    assert guide in reachable
    assert orphan not in reachable


def test_research_collection_index_routes_all_collection_members(
    tmp_path: Path,
) -> None:
    collection_index = _write(
        tmp_path,
        "docs/research/architecture-reviews/README.md",
        "# Architecture reviews\n",
    )
    nested_index = _write(
        tmp_path,
        "docs/research/architecture-reviews/2026-07-30/README.md",
        "# Snapshot\n",
    )
    snapshot = _write(
        tmp_path,
        "docs/research/architecture-reviews/2026-07-30/review.html",
        "<html></html>\n",
    )
    research_note = _write(
        tmp_path,
        "docs/research/architecture-reviews/2026-07-30/analysis.md",
        "# Analysis\n",
    )
    standalone_research = _write(
        tmp_path,
        "docs/research/standalone.md",
        "# Standalone research\n",
    )
    tracked = {
        collection_index,
        nested_index,
        snapshot,
        research_note,
        standalone_research,
    }

    required = docs_check.required_reachable_files(tracked)

    assert collection_index in required
    assert standalone_research in required
    assert nested_index not in required
    assert research_note not in required
    assert snapshot not in required


def test_change_unit_check_requires_unique_id(tmp_path: Path) -> None:
    active = _write(
        tmp_path,
        "docs/changes/feat-7-one/spec.md",
        "# Current proposal\n",
    )
    archived = _write(
        tmp_path,
        "docs/changes/archive/feat-7-old/spec.md",
        "# Old\n",
    )
    tracked = {active, archived}

    problems = docs_check.check_change_units(tmp_path, tracked)
    codes = {problem.code for problem in problems}

    assert codes == {"UNIT_ID_DUPLICATE"}


def test_research_metadata_requires_provenance_fields(tmp_path: Path) -> None:
    research = _write(
        tmp_path,
        "docs/research/comparisons/example.md",
        "---\nstatus: review-pending\nrecorded-at: 2026-07-30\n---\n\n# Example\n",
    )

    problems = docs_check.check_research_metadata(tmp_path, {research})

    assert [problem.code for problem in problems] == ["RESEARCH_METADATA"]
    assert "nano-baseline" in problems[0].message


def test_e2e_catalog_accepts_collectable_full_and_shorthand_node_ids(
    tmp_path: Path,
) -> None:
    catalog = _write(
        tmp_path,
        "docs/development/e2e-critical-paths.md",
        "# Catalog\n\n"
        "> v1 必保活当前为 2 条。\n\n"
        "## v1 必保活路径\n\n"
        "| # | 用户旅程 | 守护测试 | 归属子系统 | 引入 unit |\n"
        "|---|---|---|---|---|\n"
        "| 1 | first | `test_first.py::test_one` | gateway | feat-1 |\n"
        "| 2 | second | `test_second.py::test_two` + `::test_three` | kernel | feat-2 |\n",
    )
    collected = {
        "tests/e2e/critical_paths/test_first.py::test_one",
        "tests/e2e/critical_paths/test_second.py::test_two",
        "tests/e2e/critical_paths/test_second.py::test_three",
    }

    problems = docs_check.check_e2e_critical_path_catalog(
        tmp_path,
        {catalog},
        collected_node_ids=collected,
    )

    assert problems == []


def test_e2e_catalog_rejects_wrong_count_and_uncollectable_test(
    tmp_path: Path,
) -> None:
    catalog = _write(
        tmp_path,
        "docs/development/e2e-critical-paths.md",
        "# Catalog\n\n"
        "> v1 必保活当前为 2 条。\n\n"
        "## v1 必保活路径\n\n"
        "| # | 用户旅程 | 守护测试 | 归属子系统 | 引入 unit |\n"
        "|---|---|---|---|---|\n"
        "| 1 | journey | `test_missing.py::test_missing` | gateway | feat-1 |\n",
    )

    problems = docs_check.check_e2e_critical_path_catalog(
        tmp_path,
        {catalog},
        collected_node_ids=set(),
    )
    codes = {problem.code for problem in problems}

    assert codes == {"E2E_CATALOG_COUNT", "E2E_CATALOG_TEST"}
    assert "uncollectable test" in next(
        problem.message for problem in problems if problem.code == "E2E_CATALOG_TEST"
    )


def test_e2e_catalog_rejects_duplicate_id_and_empty_field(tmp_path: Path) -> None:
    catalog = _write(
        tmp_path,
        "docs/development/e2e-critical-paths.md",
        "# Catalog\n\n"
        "## v1 必保活路径\n\n"
        "| # | 用户旅程 | 守护测试 | 归属子系统 | 引入 unit |\n"
        "|---|---|---|---|---|\n"
        "| 1 | first | `test_first.py::test_one` | gateway | feat-1 |\n"
        "| 1 | second | `test_second.py::test_two` |  | feat-2 |\n",
    )
    collected = {
        "tests/e2e/critical_paths/test_first.py::test_one",
        "tests/e2e/critical_paths/test_second.py::test_two",
    }

    problems = docs_check.check_e2e_critical_path_catalog(
        tmp_path,
        {catalog},
        collected_node_ids=collected,
    )
    codes = {problem.code for problem in problems}

    assert codes == {"E2E_CATALOG_ID", "E2E_CATALOG_ROW"}


def test_agent_bootstrap_budget_and_adapter(tmp_path: Path) -> None:
    agents = _write(tmp_path, "AGENTS.md", "\n".join(["rule"] * 121))
    claude = _write(tmp_path, "CLAUDE.md", "@AGENTS.md\nextra\n")

    problems = docs_check.check_agent_bootstrap(tmp_path, {agents, claude})
    codes = {problem.code for problem in problems}

    assert codes == {"AGENTS_LINES", "CLAUDE_ADAPTER"}
