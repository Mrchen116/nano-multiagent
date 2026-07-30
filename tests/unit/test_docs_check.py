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


def test_agent_bootstrap_budget_and_adapter(tmp_path: Path) -> None:
    agents = _write(tmp_path, "AGENTS.md", "\n".join(["rule"] * 121))
    claude = _write(tmp_path, "CLAUDE.md", "@AGENTS.md\nextra\n")

    problems = docs_check.check_agent_bootstrap(tmp_path, {agents, claude})
    codes = {problem.code for problem in problems}

    assert codes == {"AGENTS_LINES", "CLAUDE_ADAPTER"}
