#!/usr/bin/env python3
"""Deterministic integrity checks for the repository knowledge system."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
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

COMPATIBILITY_SHIMS = {
    Path("docs/TESTING_GUIDE.md"),
    Path("docs/e2e-critical-paths.md"),
    Path("docs/operator-runbook.md"),
    Path("docs/SPEC_GUIDE.md"),
    Path("docs/可用LLM_API与联调说明.md"),
}

CURRENT_DOC_ROOTS = (
    Path("docs/product"),
    Path("docs/development"),
    Path("docs/operations"),
    Path("docs/specs"),
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

STATUS_FIELDS = (
    "Lifecycle",
    "Last checked",
    "Branch",
    "Worktree",
    "Pull request",
    "Completed",
    "Evidence",
    "Blocker",
    "Next action",
)

UNIT_DIR_RE = re.compile(
    r"^(?P<unit_id>(?:feat|bugfix|refactor|perf)-\d+)(?:-[a-z0-9][a-z0-9-]*)?$"
)

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
        if path in ROOT_ENTRYPOINTS or path in COMPATIBILITY_SHIMS:
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
            required.add(path)
        elif _is_under(path, Path("docs/archive")) and path.name == "README.md":
            required.add(path)
        elif (
            _is_active_unit_file(path)
            and path.name == "status.md"
            and len(path.parts) == 4
        ):
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
    """Require current, research, archive-index and active-status routes."""
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


def _status_table_fields(text: str) -> set[str]:
    fields: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] not in {"Field", "---"}:
            fields.add(cells[0])
    return fields


def check_change_units(root: Path, tracked: set[Path]) -> list[Problem]:
    """Check active recovery contracts and logical unit-id uniqueness."""
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

    index = Path("docs/changes/README.md")
    if index in tracked and (root / index).is_file():
        index_links = {
            link.target for link in local_links(root, index) if not link.is_directory
        }
    else:
        index_links = set()
        problems.append(
            Problem(
                "CHANGE_INDEX_MISSING",
                index,
                "active units require a tracked change index",
            )
        )
    for scope, directory in units:
        if scope != "active":
            continue
        status = Path("docs/changes") / directory / "status.md"
        if status not in tracked:
            problems.append(
                Problem(
                    "ACTIVE_STATUS_MISSING",
                    status,
                    "active or paused unit must provide status.md",
                )
            )
            continue
        if not (root / status).is_file():
            problems.append(
                Problem(
                    "ACTIVE_STATUS_MISSING",
                    status,
                    "tracked status.md is absent from the working tree",
                )
            )
            continue
        if status not in index_links:
            problems.append(
                Problem(
                    "ACTIVE_STATUS_UNINDEXED",
                    status,
                    "docs/changes/README.md must link this recovery entry",
                )
            )
        fields = _status_table_fields((root / status).read_text(encoding="utf-8"))
        missing = [field for field in STATUS_FIELDS if field not in fields]
        if missing:
            problems.append(
                Problem(
                    "ACTIVE_STATUS_FIELDS",
                    status,
                    f"missing recovery fields: {', '.join(missing)}",
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
