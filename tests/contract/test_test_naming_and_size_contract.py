"""Contract: test file naming and size guardrails.

Enforces two mechanical rules (docs/TESTING_GUIDE.md):

1. Milestone naming ban (§3 MUST NOT): no new test files whose basename matches
   ``test_m<N>*`` or ``test_m<N><letter>*`` patterns — those are one-time migration
   artifacts with no long-term regression value.

2. 400-line soft cap (§7): no newly introduced test file (relative to main branch)
   in tests/ may exceed 400 lines.  Files that already exceed the cap on main are
   grandfathered (scope boundary).

Both rules compare the working-tree state against origin/main so they catch PR
additions without burdening the existing debt.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent


def _new_test_files_vs_main() -> list[Path]:
    """Return test/*.py and test/*.tsx files added in this branch vs origin/main.

    Uses the merge-base comparison (origin/main...HEAD) so files that exist on main
    are excluded even if modified. Works-tree renames staged via git mv appear as R
    (rename) not A (add), so they are excluded from this check — only genuinely new
    filenames show up.
    """
    # Use merge-base so files renamed in this PR (git mv) appear as R not A.
    # --diff-filter=A captures files with status A (added) only.
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", "origin/main..HEAD"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        # If origin/main not available (e.g., local-only branch), skip gracefully.
        return []

    # Also check the index (staged but not yet committed changes in this session).
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    committed_added = set(result.stdout.strip().splitlines())
    staged_added = set(
        staged.stdout.strip().splitlines() if staged.returncode == 0 else []
    )
    # Exclude files staged for rename (R) or deletion (D) — those are being cleaned up.
    staged_removed = set()
    staged_full = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=RD"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    if staged_full.returncode == 0:
        for line in staged_full.stdout.strip().splitlines():
            parts = line.split("\t")
            if parts[0].startswith("R") and len(parts) >= 3:
                # R<score>\told_name\tnew_name — exclude old name (source of rename)
                staged_removed.add(parts[1])
            elif parts[0] == "D" and len(parts) >= 2:
                # D\tfilename — file deleted from staging area
                staged_removed.add(parts[1])

    # Net new = (committed added + staged added) minus files being cleaned up
    all_added = (committed_added | staged_added) - staged_removed

    return [_REPO_ROOT / p for p in all_added if re.match(r"tests/.*\.(py|tsx?)$", p)]


def _all_test_files_in_working_tree() -> list[Path]:
    """Return all test .py files under tests/ in the working tree."""
    return list(_REPO_ROOT.glob("tests/**/*.py"))


# ---------------------------------------------------------------------------
# Rule 1: no new milestone-named test files
# ---------------------------------------------------------------------------

# Pattern: test_m<digit(s)><optional-letter(s)>_... e.g. test_m9b_, test_m1_
_MILESTONE_NAME_RE = re.compile(r"^test_m\d+[a-z]*_", re.IGNORECASE)


def test_no_new_milestone_named_test_files() -> None:
    """No newly added test file basename may match test_m<N>* pattern.

    Milestone-named files are one-time migration artifacts (docs/TESTING_GUIDE.md §3
    MUST NOT). They test that a migration happened, not persistent behaviour — they
    are always green after the migration and provide zero regression value.

    Allowed exceptions: files already in origin/main (grandfathered debt).
    """
    new_files = _new_test_files_vs_main()
    violations = [p for p in new_files if _MILESTONE_NAME_RE.match(p.name)]
    if violations:
        names = "\n  ".join(str(p.relative_to(_REPO_ROOT)) for p in violations)
        pytest.fail(
            f"New test files with milestone names detected — rename to behaviour-based names:\n  {names}\n\n"
            "See docs/TESTING_GUIDE.md §3: MUST NOT use milestone numbers (test_m9*, etc.)"
        )


# ---------------------------------------------------------------------------
# Rule 2: new test files must not exceed 400 lines
# ---------------------------------------------------------------------------

_LINE_LIMIT = 400


def test_new_test_files_under_400_lines() -> None:
    """Newly introduced test files must not exceed 400 lines (docs/TESTING_GUIDE.md §7).

    Files already on main that exceed the limit are grandfathered (historical debt).
    Only files added in this branch are checked.
    """
    new_files = _new_test_files_vs_main()

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
            "See docs/TESTING_GUIDE.md §7: single file soft limit 400 lines."
        )
