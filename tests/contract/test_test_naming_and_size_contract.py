"""Contract: test file naming and size guardrails.

Enforces two mechanical rules (docs/development/testing.md):

1. Milestone naming ban (§3 MUST NOT): no test files whose basename matches
   ``test_m<N>*`` or ``test_m<N><letter>*`` patterns — those are one-time migration
   artifacts with no long-term regression value.

2. 400-line soft cap (§7): no newly introduced test file (relative to the PR base)
   may exceed 400 lines. Files that already exceed the cap on the base are
   grandfathered (scope boundary).

The naming rule covers the current tree; the size rule compares the working-tree
state against the configured PR base so additions cannot hide existing debt.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent


def _comparison_base() -> str:
    explicit = os.environ.get("NANO_TEST_BASE_REF")
    if explicit:
        return explicit
    github_base = os.environ.get("GITHUB_BASE_REF")
    return f"origin/{github_base}" if github_base else "origin/main"


def _is_test_path(path: str) -> bool:
    candidate = Path(path)
    if candidate.parts[:1] == ("tests",) and candidate.suffix == ".py":
        return True
    return candidate.parts[:4] == (
        "src",
        "IM",
        "frontend",
        "src",
    ) and candidate.name.endswith((".test.ts", ".test.tsx"))


def _new_test_files_vs_base() -> list[Path]:
    """Return test files added relative to the PR base plus local additions."""
    comparison = f"{_comparison_base()}...HEAD"
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", comparison],
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    committed_added = set(result.stdout.strip().splitlines())
    staged_added = set(staged.stdout.strip().splitlines())
    untracked_added = set(untracked.stdout.strip().splitlines())
    return [
        _REPO_ROOT / path
        for path in committed_added | staged_added | untracked_added
        if _is_test_path(path)
    ]


def _all_test_files_in_working_tree() -> list[Path]:
    """Return Python and frontend test files in the working tree."""
    frontend = _REPO_ROOT / "src" / "IM" / "frontend" / "src"
    return [
        *_REPO_ROOT.glob("tests/**/*.py"),
        *frontend.rglob("*.test.ts"),
        *frontend.rglob("*.test.tsx"),
    ]


# ---------------------------------------------------------------------------
# Rule 1: no milestone-named test files
# ---------------------------------------------------------------------------

# Pattern: test_m<digit(s)><optional-letter(s)>_... e.g. test_m9b_, test_m1_
_MILESTONE_NAME_RE = re.compile(r"^test_m\d+[a-z]*_", re.IGNORECASE)


def test_no_milestone_named_test_files() -> None:
    """Test filenames must describe behavior rather than delivery milestones."""
    violations = [
        path
        for path in _all_test_files_in_working_tree()
        if _MILESTONE_NAME_RE.match(path.name)
    ]
    if violations:
        names = "\n  ".join(str(p.relative_to(_REPO_ROOT)) for p in violations)
        pytest.fail(
            f"Test files with milestone names detected — rename to behaviour-based names:\n  {names}\n\n"
            "See docs/development/testing.md §3: MUST NOT use milestone numbers (test_m9*, etc.)"
        )


# ---------------------------------------------------------------------------
# Rule 2: new test files must not exceed 400 lines
# ---------------------------------------------------------------------------

_LINE_LIMIT = 400


def test_new_test_files_under_400_lines() -> None:
    """Newly introduced test files must not exceed 400 lines (docs/development/testing.md §7).

    Files already on main that exceed the limit are grandfathered (historical debt).
    Only files added in this branch are checked.
    """
    new_files = _new_test_files_vs_base()

    violations: list[tuple[Path, int]] = []
    for path in new_files:
        if not path.exists():
            continue
        try:
            line_count = sum(1 for _ in path.open(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if line_count > _LINE_LIMIT:
            violations.append((path, line_count))

    if violations:
        detail = "\n  ".join(
            f"{p.relative_to(_REPO_ROOT)} ({n} lines)" for p, n in violations
        )
        pytest.fail(
            f"New test files exceed {_LINE_LIMIT}-line soft cap — split by behaviour:\n  {detail}\n\n"
            "See docs/development/testing.md §7: single file soft limit 400 lines."
        )
