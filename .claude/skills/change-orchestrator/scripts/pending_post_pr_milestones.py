#!/usr/bin/env python3
"""List unstarted milestone directories added by a post-PR design revision."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


MILESTONE_DIR = re.compile(r"^M(?P<number>[1-9][0-9]*)-.+$")


def design_milestone_numbers(unit_doc_root: Path, unit_id: str) -> set[int]:
    """Read milestone numbers from the first column of the design table."""
    design_path = unit_doc_root / "design.md"
    if not design_path.is_file():
        raise ValueError(f"post-PR full unit is missing design.md: {design_path}")
    row = re.compile(rf"^\|\s*{re.escape(unit_id)}-M(?P<number>[1-9][0-9]*)\s*\|")
    numbers = {
        int(match.group("number"))
        for line in design_path.read_text(encoding="utf-8").splitlines()
        if (match := row.match(line))
    }
    if not numbers:
        raise ValueError(f"design milestone table is empty for {unit_id}")
    return numbers


def pending_milestones(unit_doc_root: Path, unit_id: str) -> list[str]:
    """Return milestone directories containing no worker output yet."""
    if not unit_doc_root.is_dir():
        raise ValueError(f"unit document root does not exist: {unit_doc_root}")

    expected_numbers = design_milestone_numbers(unit_doc_root, unit_id)
    candidates: dict[int, str] = {}
    for child in unit_doc_root.iterdir():
        match = MILESTONE_DIR.fullmatch(child.name)
        if child.is_dir() and match:
            number = int(match.group("number"))
            if number in candidates:
                raise ValueError(f"duplicate milestone directory M{number}")
            candidates[number] = child.name

    actual_numbers = set(candidates)
    if actual_numbers != expected_numbers:
        missing = sorted(expected_numbers - actual_numbers)
        extra = sorted(actual_numbers - expected_numbers)
        raise ValueError(
            f"design/directory milestone mismatch; missing={missing}, extra={extra}"
        )

    pending: list[str] = []
    for _, name in sorted(candidates.items()):
        milestone_dir = unit_doc_root / name
        worker_outputs = [
            entry for entry in milestone_dir.iterdir() if entry.name != ".gitkeep"
        ]
        if not worker_outputs:
            if not (milestone_dir / ".gitkeep").is_file():
                raise ValueError(
                    f"pending milestone is not Git-trackable: {milestone_dir}"
                )
            pending.append(name)
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-doc-root", type=Path, required=True)
    parser.add_argument("--unit-id", required=True)
    args = parser.parse_args()

    try:
        pending = pending_milestones(args.unit_doc_root, args.unit_id)
    except ValueError as error:
        parser.error(str(error))
    print("\n".join(pending))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
