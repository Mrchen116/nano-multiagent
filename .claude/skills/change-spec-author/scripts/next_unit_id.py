#!/usr/bin/env python3
"""Return the next global change-unit id across active and archived units."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


UNIT_DIR_PATTERN = re.compile(
    r"^(?:feat|bugfix|refactor|perf|docs|chore)-(\d+)(?:-|$)"
)
CHANGE_TYPES = ("feat", "bugfix", "refactor", "perf", "docs", "chore")


def existing_numbers(changes_dir: Path) -> set[int]:
    """Collect unit numbers from active and archived unit directories."""
    numbers: set[int] = set()
    for parent in (changes_dir, changes_dir / "archive"):
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            match = UNIT_DIR_PATTERN.match(child.name)
            if match:
                numbers.add(int(match.group(1)))
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Allocate the next global docs/changes unit id."
    )
    parser.add_argument("change_type", choices=CHANGE_TYPES)
    parser.add_argument(
        "--changes-dir",
        type=Path,
        default=Path("docs/changes"),
        help="Path to docs/changes (default: docs/changes).",
    )
    args = parser.parse_args()

    if not args.changes_dir.is_dir():
        parser.error(f"changes directory does not exist: {args.changes_dir}")

    next_number = max(existing_numbers(args.changes_dir), default=0) + 1
    print(f"{args.change_type}-{next_number}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
