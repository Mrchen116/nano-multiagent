#!/usr/bin/env python3
"""Require a unit PR's change directory to be uniquely archived."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


UNIT_BRANCH = re.compile(
    r"^unit/(?P<unit_id>(?:feat|bugfix|refactor|perf)-\d+)(?:-.+)?$"
)
SCOPES = (
    ("active", Path("docs/changes")),
    ("archive", Path("docs/changes/archive")),
    ("retired", Path("docs/changes/retired")),
)


def _unit_directories(repo_root: Path, unit_id: str) -> list[tuple[str, Path]]:
    matches: list[tuple[str, Path]] = []
    for scope, relative_root in SCOPES:
        root = repo_root / relative_root
        if not root.is_dir():
            continue
        matches.extend(
            (scope, path.relative_to(repo_root))
            for path in root.iterdir()
            if path.is_dir()
            and (path.name == unit_id or path.name.startswith(f"{unit_id}-"))
        )
    return sorted(matches, key=lambda match: match[1].as_posix())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--head-ref",
        default=os.environ.get("GITHUB_HEAD_REF", ""),
        help="Pull request head branch (defaults to GITHUB_HEAD_REF)",
    )
    return parser.parse_args()


def main() -> int:
    """Check the current repository for the branch's archived change unit."""
    head_ref = _parse_args().head_ref
    if not head_ref.startswith("unit/"):
        print(f"Skipping change-unit archive check for branch: {head_ref or '<empty>'}")
        return 0

    match = UNIT_BRANCH.fullmatch(head_ref)
    if match is None:
        print(
            f"Invalid unit branch name: {head_ref}. Expected unit/<type>-<number>.",
            file=sys.stderr,
        )
        return 1

    unit_id = match.group("unit_id")
    matches = _unit_directories(Path.cwd(), unit_id)
    if not matches:
        print(
            f"No change unit found for {unit_id}; expected "
            f"docs/changes/archive/{unit_id}-*.",
            file=sys.stderr,
        )
        return 1
    if len(matches) > 1:
        locations = ", ".join(path.as_posix() for _, path in matches)
        print(
            f"Change unit {unit_id} exists in multiple locations: {locations}. "
            "Keep exactly one archived directory.",
            file=sys.stderr,
        )
        return 1

    scope, path = matches[0]
    if scope != "archive":
        print(
            f"Change unit {unit_id} is still {scope} at {path.as_posix()}; "
            f"move it to docs/changes/archive/ before delivery.",
            file=sys.stderr,
        )
        return 1

    print(f"Change unit {unit_id} is archived at {path.as_posix()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
