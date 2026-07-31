#!/usr/bin/env python3
"""Deterministic integrity checks for the repository knowledge system."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from markdown_it import MarkdownIt

AGENTS_MAX_LINES = 120
AGENTS_MAX_BYTES = 12 * 1024

ROOT_ENTRYPOINTS = {
    Path("AGENTS.md"),
    Path("README.md"),
    Path("SPEC.md"),
    Path("docs/README.md"),
    Path("docs/changes/README.md"),
}

CURRENT_DOC_ROOTS = (
    Path("docs/product"),
    Path("docs/development"),
    Path("docs/operations"),
    Path("docs/specs"),
)

RESEARCH_COLLECTION_ROOTS = (
    Path("docs/research/architecture-reviews"),
    Path("docs/research/brainstorms"),
    Path("docs/research/comparisons"),
    Path("docs/research/studies"),
)

RETIRED_LINK_PREFIXES = (
    Path("COMMENTING_GUIDE.md"),
    Path("ROADMAP.md"),
    Path("TASKS.md"),
    Path("PROGRESS.md"),
    Path("LOGBOOK.md"),
    Path("TASKS"),
    Path("PROGRESS"),
    Path("ACCEPTANCE"),
    Path("docs/TESTING_GUIDE.md"),
    Path("docs/e2e-critical-paths.md"),
    Path("docs/operator-runbook.md"),
    Path("docs/SPEC_GUIDE.md"),
    Path("docs/可用LLM_API与联调说明.md"),
    Path("docs/changes/readme.md"),
    Path("docs/需求.md"),
    Path("docs/IM前端蓝图.md"),
    Path("docs/IM-user-stream-migration-plan.md"),
    Path("docs/spec-implementation-conflicts.md"),
    Path("docs/内核设计细化"),
    Path("docs/tools-diff-cc"),
    Path("docs/kernel-diff-cc"),
    Path("docs/brainstorms"),
    Path("docs/architecture-reviews"),
)

RESEARCH_METADATA_FIELDS = (
    "status",
    "recorded-at",
    "nano-baseline",
    "source-baseline",
    "current-owner",
)

RESEARCH_STATUSES = {
    "research-in-progress",
    "research-snapshot",
    "review-pending",
    "adopted",
    "partially-adopted",
    "superseded",
}

SPEC_ROOT = Path("docs/specs")
SPEC_AREA_TABLE_COLUMNS = ("Area", "Covers", "Requirements")
SPEC_AREA_LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")
UNIT_DIR_RE = re.compile(
    r"^(?P<unit_id>(?:feat|bugfix|refactor|perf)-\d+)(?:-[a-z0-9][a-z0-9-]*)?$"
)
E2E_CRITICAL_PATH_CATALOG = Path("docs/development/e2e-critical-paths.md")
E2E_CRITICAL_PATH_TEST_ROOT = Path("tests/e2e/critical_paths")
E2E_CATALOG_COLUMNS = ("#", "用户旅程", "守护测试", "归属子系统", "引入 unit")
E2E_CATALOG_COUNT_RE = re.compile(r"v1 必保活当前为\s*(\d+)\s*条")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

_MARKDOWN = MarkdownIt("commonmark")


@dataclass(frozen=True)
class Problem:
    """One deterministic documentation integrity failure."""

    code: str
    path: Path
    message: str
    line: int | None = None

    def render(self) -> str:
        """Render one stable CLI diagnostic."""
        location = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"[{self.code}] {location}: {self.message}"


@dataclass(frozen=True)
class LocalLink:
    """A repository-local Markdown link resolved relative to its source."""

    source: Path
    href: str
    target: Path
    is_directory: bool
    line: int | None


def git_tracked_files(root: Path) -> set[Path]:
    """Return tracked paths without Git's non-ASCII quoting."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return {Path(os.fsdecode(item)) for item in result.stdout.split(b"\0") if item}


def _is_under(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _is_active_unit_file(path: Path) -> bool:
    return (
        len(path.parts) >= 4
        and path.parts[:2] == ("docs", "changes")
        and path.parts[2] not in {"archive", "retired"}
    )


def maintained_markdown_sources(tracked: set[Path]) -> set[Path]:
    """Return Markdown whose links are maintained as live repository routes."""
    sources: set[Path] = set()
    for path in tracked:
        if path.suffix.lower() != ".md":
            continue
        if path in ROOT_ENTRYPOINTS:
            sources.add(path)
            continue
        if any(_is_under(path, root) for root in CURRENT_DOC_ROOTS):
            sources.add(path)
            continue
        if _is_under(path, Path("docs/research")):
            sources.add(path)
            continue
        if _is_under(path, Path("docs/archive")) and path.name == "README.md":
            sources.add(path)
            continue
        if _is_active_unit_file(path):
            sources.add(path)
            continue
        if _is_under(path, Path(".claude/skills")):
            sources.add(path)
    return sources


def _resolve_local_link(
    root: Path,
    source: Path,
    href: str,
    line: int | None,
) -> LocalLink | None:
    try:
        parsed = urlsplit(href)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        return None

    target_path = unquote(parsed.path)
    absolute = (root / source.parent / target_path).resolve()
    try:
        target = absolute.relative_to(root)
    except ValueError:
        return None

    return LocalLink(
        source=source,
        href=href,
        target=target,
        is_directory=target_path.endswith("/") or absolute.is_dir(),
        line=line,
    )


def local_links(root: Path, source: Path) -> list[LocalLink]:
    """Parse repository-local links from Markdown, excluding code blocks."""
    text = (root / source).read_text(encoding="utf-8")
    links: list[LocalLink] = []
    for token in _MARKDOWN.parse(text):
        if token.type != "inline" or not token.children:
            continue
        line = token.map[0] + 1 if token.map else None
        for child in token.children:
            if child.type == "link_open":
                href = child.attrGet("href") or ""
            elif child.type == "image":
                href = child.attrGet("src") or ""
            else:
                continue
            link = _resolve_local_link(
                root,
                source,
                href,
                line,
            )
            if link is not None:
                links.append(link)
    return links


def _target_is_tracked(link: LocalLink, tracked: set[Path]) -> bool:
    if not link.is_directory:
        return link.target in tracked
    return any(path.is_relative_to(link.target) for path in tracked)


def _is_retired_target(path: Path) -> bool:
    return any(_is_under(path, prefix) for prefix in RETIRED_LINK_PREFIXES)


def check_local_links(root: Path, tracked: set[Path]) -> list[Problem]:
    """Check maintained local links and deny new references to retired routes."""
    problems: list[Problem] = []
    for source in sorted(maintained_markdown_sources(tracked)):
        if not (root / source).is_file():
            problems.append(
                Problem("SOURCE_MISSING", source, "tracked Markdown source is absent")
            )
            continue
        for link in local_links(root, source):
            if _is_retired_target(link.target):
                problems.append(
                    Problem(
                        "RETIRED_LINK",
                        source,
                        f"{link.href!r} points to retired route {link.target}",
                        link.line,
                    )
                )
                continue
            if not _target_is_tracked(link, tracked):
                problems.append(
                    Problem(
                        "BROKEN_LINK",
                        source,
                        f"{link.href!r} does not resolve to a tracked file or directory",
                        link.line,
                    )
                )
    return problems


def required_reachable_files(tracked: set[Path]) -> set[Path]:
    """Return files that must be discoverable from the resident bootstrap."""
    required = set(ROOT_ENTRYPOINTS)
    for path in tracked:
        if path.suffix.lower() not in {".md", ".html"}:
            continue
        if any(_is_under(path, root) for root in CURRENT_DOC_ROOTS):
            required.add(path)
        elif _is_under(path, Path("docs/research")):
            covered_by_collection = any(
                path != collection_root / "README.md"
                and _is_under(path, collection_root)
                and collection_root / "README.md" in tracked
                for collection_root in RESEARCH_COLLECTION_ROOTS
            )
            if not covered_by_collection:
                required.add(path)
        elif _is_under(path, Path("docs/archive")) and path.name == "README.md":
            required.add(path)
    return required


def reachable_files(root: Path, tracked: set[Path]) -> set[Path]:
    """Traverse maintained Markdown routes from ``AGENTS.md``."""
    maintained = maintained_markdown_sources(tracked)
    seen: set[Path] = set()
    queue = [Path("AGENTS.md")]

    while queue:
        path = queue.pop()
        if path in seen or path not in tracked:
            continue
        seen.add(path)
        if (
            path not in maintained
            or path.suffix.lower() != ".md"
            or not (root / path).is_file()
        ):
            continue
        for link in local_links(root, path):
            if link.is_directory:
                readme = link.target / "README.md"
                if readme in tracked and readme not in seen:
                    queue.append(readme)
            elif link.target in tracked and link.target not in seen:
                queue.append(link.target)
    return seen


def check_reachability(root: Path, tracked: set[Path]) -> list[Problem]:
    """Require current, research and archive-index routes."""
    seen = reachable_files(root, tracked)
    return [
        Problem(
            "UNREACHABLE",
            path,
            "required knowledge entry is not reachable from AGENTS.md",
        )
        for path in sorted(required_reachable_files(tracked) - seen)
    ]


def _unit_directories(tracked: set[Path]) -> list[tuple[str, str]]:
    units: set[tuple[str, str]] = set()
    for path in tracked:
        parts = path.parts
        if len(parts) < 4 or parts[:2] != ("docs", "changes"):
            continue
        if parts[2] in {"archive", "retired"}:
            if len(parts) >= 5:
                units.add((parts[2], parts[3]))
        else:
            units.add(("active", parts[2]))
    return sorted(units)


def check_change_units(root: Path, tracked: set[Path]) -> list[Problem]:
    """Check logical unit-id uniqueness across lifecycle directories."""
    problems: list[Problem] = []
    by_id: dict[str, list[tuple[str, str]]] = {}
    units = _unit_directories(tracked)
    for scope, directory in units:
        match = UNIT_DIR_RE.fullmatch(directory)
        path = (
            Path("docs/changes") / directory
            if scope == "active"
            else Path("docs/changes") / scope / directory
        )
        if match is None:
            problems.append(
                Problem(
                    "UNIT_NAME",
                    path,
                    "unit directory must match <type>-<id>[-<short-desc>]",
                )
            )
            continue
        by_id.setdefault(match.group("unit_id"), []).append((scope, directory))

    for unit_id, locations in sorted(by_id.items()):
        if len(locations) > 1:
            detail = ", ".join(f"{scope}:{directory}" for scope, directory in locations)
            problems.append(
                Problem(
                    "UNIT_ID_DUPLICATE",
                    Path("docs/changes"),
                    f"{unit_id} resolves to multiple units: {detail}",
                )
            )

    return problems


def _research_leaf_markdown(tracked: set[Path]) -> list[Path]:
    return sorted(
        path
        for path in tracked
        if path.suffix.lower() == ".md"
        and _is_under(path, Path("docs/research"))
        and path.name != "README.md"
        and path != Path("docs/research/upstreams.md")
    )


def _frontmatter(text: str) -> dict[str, object] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    parsed = yaml.safe_load(text[4:end])
    return parsed if isinstance(parsed, dict) else None


def check_research_metadata(root: Path, tracked: set[Path]) -> list[Problem]:
    """Require provenance and lifecycle metadata on research leaf pages."""
    problems: list[Problem] = []
    for path in _research_leaf_markdown(tracked):
        if not (root / path).is_file():
            problems.append(
                Problem(
                    "RESEARCH_SOURCE_MISSING",
                    path,
                    "tracked research leaf is absent from the working tree",
                )
            )
            continue
        metadata = _frontmatter((root / path).read_text(encoding="utf-8"))
        if metadata is None:
            problems.append(
                Problem(
                    "RESEARCH_FRONTMATTER",
                    path,
                    "research leaf must start with YAML frontmatter",
                )
            )
            continue
        missing = [
            field
            for field in RESEARCH_METADATA_FIELDS
            if not str(metadata.get(field, "")).strip()
        ]
        if missing:
            problems.append(
                Problem(
                    "RESEARCH_METADATA",
                    path,
                    f"missing metadata: {', '.join(missing)}",
                )
            )
        status = str(metadata.get("status", "")).strip()
        if status and status not in RESEARCH_STATUSES:
            problems.append(
                Problem(
                    "RESEARCH_STATUS",
                    path,
                    f"unsupported research status {status!r}",
                )
            )
        recorded_at = str(metadata.get("recorded-at", "")).strip()
        if recorded_at:
            try:
                date.fromisoformat(recorded_at)
            except ValueError:
                problems.append(
                    Problem(
                        "RESEARCH_DATE",
                        path,
                        f"recorded-at must be YYYY-MM-DD, got {recorded_at!r}",
                    )
                )
    return problems


def _markdown_table_cells(line: str) -> tuple[str, ...] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return tuple(
        cell.replace(r"\|", "|").strip()
        for cell in re.split(r"(?<!\\)\|", stripped[1:-1])
    )


def _requirement_heading_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    tokens = _MARKDOWN.parse(text)
    return sum(
        1
        for index, token in enumerate(tokens[:-1])
        if token.type == "heading_open"
        and token.tag == "h3"
        and tokens[index + 1].type == "inline"
        and tokens[index + 1].content.startswith("Requirement:")
    )


def _canonical_spec_entries(tracked: set[Path]) -> list[Path]:
    return sorted(
        path
        for path in tracked
        if path.name == "spec.md" and path.parent.parent == SPEC_ROOT
    )


def check_spec_area_indexes(root: Path, tracked: set[Path]) -> list[Problem]:
    """Check package area coverage and derived Requirement counts."""
    problems: list[Problem] = []
    for entry in _canonical_spec_entries(tracked):
        entry_path = root / entry
        if not entry_path.is_file():
            problems.append(
                Problem(
                    "SPEC_AREA_SOURCE",
                    entry,
                    "tracked package spec entry is absent",
                )
            )
            continue

        lines = entry_path.read_text(encoding="utf-8").splitlines()
        heading_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.strip() == "## Canonical Areas"
            ),
            None,
        )
        if heading_index is None:
            problems.append(
                Problem(
                    "SPEC_AREA_TABLE",
                    entry,
                    "missing '## Canonical Areas' section",
                )
            )
            continue

        header_index: int | None = None
        for index in range(heading_index + 1, len(lines)):
            if lines[index].startswith("## "):
                break
            if _markdown_table_cells(lines[index]) == SPEC_AREA_TABLE_COLUMNS:
                header_index = index
                break
        if header_index is None:
            problems.append(
                Problem(
                    "SPEC_AREA_TABLE",
                    entry,
                    "missing canonical area table or expected three-column header",
                    heading_index + 1,
                )
            )
            continue

        separator = (
            _markdown_table_cells(lines[header_index + 1])
            if header_index + 1 < len(lines)
            else None
        )
        if (
            separator is None
            or len(separator) != len(SPEC_AREA_TABLE_COLUMNS)
            or any(re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator)
        ):
            problems.append(
                Problem(
                    "SPEC_AREA_TABLE",
                    entry,
                    "table header must be followed by a three-column separator",
                    header_index + 2,
                )
            )

        rows: list[tuple[int, tuple[str, ...]]] = []
        for index in range(header_index + 2, len(lines)):
            cells = _markdown_table_cells(lines[index])
            if cells is None:
                break
            rows.append((index + 1, cells))

        indexed_areas: set[Path] = set()
        for line_number, cells in rows:
            if len(cells) != len(SPEC_AREA_TABLE_COLUMNS):
                problems.append(
                    Problem(
                        "SPEC_AREA_ROW",
                        entry,
                        f"expected three columns, found {len(cells)}",
                        line_number,
                    )
                )
                continue

            area_match = SPEC_AREA_LINK_RE.fullmatch(cells[0])
            if area_match is None:
                problems.append(
                    Problem(
                        "SPEC_AREA_ROW",
                        entry,
                        "Area cell must contain one Markdown link",
                        line_number,
                    )
                )
                continue

            area_name, href = area_match.groups()
            link = _resolve_local_link(root, entry, href, line_number)
            if (
                link is None
                or link.is_directory
                or link.target.parent != entry.parent
                or link.target.name == "spec.md"
                or link.target.suffix.lower() != ".md"
            ):
                problems.append(
                    Problem(
                        "SPEC_AREA_TARGET",
                        entry,
                        f"{area_name} must link to an area Markdown file in {entry.parent}",
                        line_number,
                    )
                )
                continue

            if link.target in indexed_areas:
                problems.append(
                    Problem(
                        "SPEC_AREA_DUPLICATE",
                        entry,
                        f"{link.target.name} is indexed more than once",
                        line_number,
                    )
                )
            indexed_areas.add(link.target)

            if link.target not in tracked or not (root / link.target).is_file():
                problems.append(
                    Problem(
                        "SPEC_AREA_TARGET",
                        entry,
                        f"{area_name} points to missing tracked area {link.target}",
                        line_number,
                    )
                )
                continue

            declared_count = cells[2]
            if not declared_count.isdigit():
                problems.append(
                    Problem(
                        "SPEC_REQUIREMENT_COUNT",
                        entry,
                        f"{area_name} Requirement count must be an integer",
                        line_number,
                    )
                )
                continue
            actual_count = _requirement_heading_count(root / link.target)
            if int(declared_count) != actual_count:
                problems.append(
                    Problem(
                        "SPEC_REQUIREMENT_COUNT",
                        entry,
                        f"{area_name} declares {declared_count} Requirements, "
                        f"but {link.target.name} contains {actual_count}",
                        line_number,
                    )
                )

        package_area_files = {
            path
            for path in tracked
            if path.parent == entry.parent
            and path.name != "spec.md"
            and path.suffix.lower() == ".md"
        }
        for missing in sorted(package_area_files - indexed_areas):
            problems.append(
                Problem(
                    "SPEC_AREA_UNINDEXED",
                    entry,
                    f"{missing.name} is not listed in Canonical Areas",
                )
            )
    return problems


def _catalog_test_node_ids(test_cell: str) -> tuple[str, ...]:
    nodes: list[str] = []
    current_file: Path | None = None
    for code in INLINE_CODE_RE.findall(test_cell):
        if code.startswith("::"):
            if current_file is not None:
                nodes.append(f"{current_file.as_posix()}{code}")
            continue
        if ".py::" not in code:
            continue
        file_text, test_name = code.split("::", 1)
        file_path = Path(file_text)
        if file_path.parent == Path("."):
            current_file = E2E_CRITICAL_PATH_TEST_ROOT / file_path
        elif file_path.is_relative_to(E2E_CRITICAL_PATH_TEST_ROOT):
            current_file = file_path
        else:
            continue
        nodes.append(f"{current_file.as_posix()}::{test_name}")
    return tuple(nodes)


def _collect_e2e_test_node_ids(root: Path) -> tuple[set[str], Problem | None]:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                E2E_CRITICAL_PATH_TEST_ROOT.as_posix(),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return set(), Problem(
            "E2E_CATALOG_COLLECTION",
            E2E_CRITICAL_PATH_TEST_ROOT,
            "pytest collection exceeded 30 seconds",
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        summary = detail[-1] if detail else f"pytest exited {result.returncode}"
        return set(), Problem(
            "E2E_CATALOG_COLLECTION",
            E2E_CRITICAL_PATH_TEST_ROOT,
            summary,
        )
    prefix = f"{E2E_CRITICAL_PATH_TEST_ROOT.as_posix()}/"
    nodes = {
        line.strip()
        for line in result.stdout.splitlines()
        if line.startswith(prefix) and "::" in line
    }
    if not nodes:
        return set(), Problem(
            "E2E_CATALOG_COLLECTION",
            E2E_CRITICAL_PATH_TEST_ROOT,
            "pytest collected no critical-path tests",
        )
    return nodes, None


def _node_is_collected(node: str, collected: set[str]) -> bool:
    return node in collected or any(item.startswith(f"{node}[") for item in collected)


def check_e2e_critical_path_catalog(
    root: Path,
    tracked: set[Path],
    *,
    collected_node_ids: set[str] | None = None,
) -> list[Problem]:
    """Check the structural contract between the critical-path table and pytest."""
    catalog = E2E_CRITICAL_PATH_CATALOG
    if catalog not in tracked or not (root / catalog).is_file():
        return []

    text = (root / catalog).read_text(encoding="utf-8")
    lines = text.splitlines()
    heading_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip() == "## v1 必保活路径"
        ),
        None,
    )
    if heading_index is None:
        return [
            Problem(
                "E2E_CATALOG_TABLE",
                catalog,
                "missing '## v1 必保活路径' section",
            )
        ]

    header_index: int | None = None
    for index in range(heading_index + 1, len(lines)):
        if lines[index].startswith("## "):
            break
        if _markdown_table_cells(lines[index]) == E2E_CATALOG_COLUMNS:
            header_index = index
            break
    if header_index is None:
        return [
            Problem(
                "E2E_CATALOG_TABLE",
                catalog,
                "missing critical-path table or expected five-column header",
                heading_index + 1,
            )
        ]

    problems: list[Problem] = []
    separator = (
        _markdown_table_cells(lines[header_index + 1])
        if header_index + 1 < len(lines)
        else None
    )
    if (
        separator is None
        or len(separator) != len(E2E_CATALOG_COLUMNS)
        or any(re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator)
    ):
        problems.append(
            Problem(
                "E2E_CATALOG_TABLE",
                catalog,
                "table header must be followed by a five-column separator",
                header_index + 2,
            )
        )

    rows: list[tuple[int, tuple[str, ...]]] = []
    for index in range(header_index + 2, len(lines)):
        cells = _markdown_table_cells(lines[index])
        if cells is None:
            break
        rows.append((index + 1, cells))

    count_match = E2E_CATALOG_COUNT_RE.search(text)
    if count_match is not None and int(count_match.group(1)) != len(rows):
        count_line = text[: count_match.start()].count("\n") + 1
        problems.append(
            Problem(
                "E2E_CATALOG_COUNT",
                catalog,
                f"declares {count_match.group(1)} paths but table has {len(rows)} rows",
                count_line,
            )
        )

    seen_ids: set[str] = set()
    referenced: list[tuple[int, str, str]] = []
    for line_number, cells in rows:
        if len(cells) != len(E2E_CATALOG_COLUMNS):
            problems.append(
                Problem(
                    "E2E_CATALOG_ROW",
                    catalog,
                    f"expected five columns, found {len(cells)}",
                    line_number,
                )
            )
            continue
        row_id = cells[0]
        if not row_id.isdigit():
            problems.append(
                Problem(
                    "E2E_CATALOG_ID",
                    catalog,
                    f"row id must be an integer, got {row_id!r}",
                    line_number,
                )
            )
        elif row_id in seen_ids:
            problems.append(
                Problem(
                    "E2E_CATALOG_ID",
                    catalog,
                    f"duplicate row id {row_id}",
                    line_number,
                )
            )
        seen_ids.add(row_id)

        missing_fields = [
            E2E_CATALOG_COLUMNS[index] for index, value in enumerate(cells) if not value
        ]
        if missing_fields:
            problems.append(
                Problem(
                    "E2E_CATALOG_ROW",
                    catalog,
                    f"row {row_id or '?'} has empty fields: {', '.join(missing_fields)}",
                    line_number,
                )
            )

        node_ids = _catalog_test_node_ids(cells[2])
        if not node_ids:
            problems.append(
                Problem(
                    "E2E_CATALOG_TEST",
                    catalog,
                    f"row {row_id or '?'} must reference a critical-path pytest node id",
                    line_number,
                )
            )
        referenced.extend((line_number, row_id, node) for node in node_ids)

    if not referenced:
        return problems
    if collected_node_ids is None:
        collected_node_ids, collection_problem = _collect_e2e_test_node_ids(root)
        if collection_problem is not None:
            problems.append(collection_problem)
            return problems
    for line_number, row_id, node in referenced:
        if not _node_is_collected(node, collected_node_ids):
            problems.append(
                Problem(
                    "E2E_CATALOG_TEST",
                    catalog,
                    f"row {row_id} references uncollectable test {node}",
                    line_number,
                )
            )
    return problems


def check_agent_bootstrap(root: Path, tracked: set[Path]) -> list[Problem]:
    """Keep resident instructions bounded and the Claude adapter minimal."""
    problems: list[Problem] = []
    agents = Path("AGENTS.md")
    claude = Path("CLAUDE.md")
    if agents not in tracked:
        problems.append(Problem("AGENTS_MISSING", agents, "AGENTS.md must be tracked"))
    elif not (root / agents).is_file():
        problems.append(
            Problem("AGENTS_MISSING", agents, "tracked AGENTS.md is absent")
        )
    else:
        data = (root / agents).read_bytes()
        line_count = len(data.decode("utf-8").splitlines())
        if line_count > AGENTS_MAX_LINES:
            problems.append(
                Problem(
                    "AGENTS_LINES",
                    agents,
                    f"{line_count} lines exceeds budget {AGENTS_MAX_LINES}",
                )
            )
        if len(data) > AGENTS_MAX_BYTES:
            problems.append(
                Problem(
                    "AGENTS_BYTES",
                    agents,
                    f"{len(data)} bytes exceeds budget {AGENTS_MAX_BYTES}",
                )
            )

    if claude not in tracked:
        problems.append(Problem("CLAUDE_MISSING", claude, "CLAUDE.md must be tracked"))
    elif not (root / claude).is_file():
        problems.append(
            Problem("CLAUDE_MISSING", claude, "tracked CLAUDE.md is absent")
        )
    else:
        content = (root / claude).read_text(encoding="utf-8")
        if content not in {"@AGENTS.md", "@AGENTS.md\n"}:
            problems.append(
                Problem(
                    "CLAUDE_ADAPTER",
                    claude,
                    "CLAUDE.md must contain only @AGENTS.md",
                )
            )
    return problems


def run_checks(root: Path, tracked: set[Path] | None = None) -> list[Problem]:
    """Run all repository knowledge-system checks."""
    tracked = git_tracked_files(root) if tracked is None else tracked
    problems = [
        *check_local_links(root, tracked),
        *check_reachability(root, tracked),
        *check_change_units(root, tracked),
        *check_research_metadata(root, tracked),
        *check_spec_area_indexes(root, tracked),
        *check_e2e_critical_path_catalog(root, tracked),
        *check_agent_bootstrap(root, tracked),
    ]
    return sorted(
        problems,
        key=lambda problem: (
            str(problem.path),
            problem.line or 0,
            problem.code,
            problem.message,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check nano-multiagent documentation integrity."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root (defaults to the checkout containing this script)",
    )
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    tracked = git_tracked_files(root)
    problems = run_checks(root, tracked)
    if problems:
        print(f"documentation integrity failed: {len(problems)} problem(s)")
        for problem in problems:
            print(problem.render())
        return 1

    print(
        "documentation integrity passed: "
        f"{len(maintained_markdown_sources(tracked))} maintained Markdown sources, "
        f"{len(required_reachable_files(tracked))} required routes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
