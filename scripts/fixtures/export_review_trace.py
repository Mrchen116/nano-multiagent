#!/usr/bin/env python3
"""Export prompt-free nano_approval v1 facts from one explicit isolated runtime.

This diagnostic reads the public JSON-domain medium; it never connects to a
running process, restores a Session, or reads delegated evidence/configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_FIELDS = {
    "time",
    "callId",
    "tool",
    "source",
    "decision",
    "consecutive",
    "total",
    "reviewer",
    "rules",
    "elapsedMs",
    "usage",
    "recovery",
    "reviewId",
    "metadata",
}


def export(
    runtime: Path, *, session: str | None = None, call_id: str | None = None
) -> list[dict[str, Any]]:
    """Read only the approval sessions table below the supplied runtime root.

    Args:
        runtime: Explicit isolated E2E root, not a user configuration directory.
        session: Optional exact Session ID.
        call_id: Optional exact tool call ID.
    Returns:
        Prompt-free rows with source locators. Old rows need no recovery field.
    """
    root = runtime.resolve(strict=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/nano_approval/sessions/*.json")):
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("Approval record escaped the isolated runtime root")
        if session and path.stem != session:
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("version") != 1 or not isinstance(document.get("record"), list):
            raise ValueError(f"Unsupported approval document: {path}")
        for row in document["record"]:
            if call_id and row.get("callId") != call_id:
                continue
            rows.append(
                {
                    "sessionId": path.stem,
                    "locator": str(path.relative_to(root)),
                    **{key: value for key, value in row.items() if key in _FIELDS},
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--session")
    parser.add_argument("--call-id")
    parser.add_argument(
        "--sha", required=True, help="Exact build SHA supplied by the caller"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "build_sha": args.sha,
                "runtime": str(args.runtime.resolve()),
                "rows": export(
                    args.runtime, session=args.session, call_id=args.call_id
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
