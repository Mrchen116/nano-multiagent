"""Run the M106 IM↔Gateway realistic acceptance suite and print evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_TEST = REPO_ROOT / "tests" / "acceptance" / "test_im_gateway_real_acceptance.py"


def main() -> int:
    """Execute the M106 acceptance tests and emit a compact evidence summary.

    Returns:
        Process exit code from the acceptance test run.
    """

    if not ACCEPTANCE_TEST.is_file():
        raise FileNotFoundError(f"acceptance test missing: {ACCEPTANCE_TEST}")
    print(
        json.dumps(
            {
                "milestone": "M106",
                "repo_root": str(REPO_ROOT),
                "acceptance_test": str(ACCEPTANCE_TEST),
                "checks": [
                    "device bind start+confirm",
                    "gateway websocket register+heartbeat",
                    "relay.message -> gateway inbound pipeline -> outbound reply",
                    "node.delivery_receipt sent/completed",
                    "node.report capture",
                    "product-gap assertion: SSE still lacks relay receipt progress events",
                ],
            },
            ensure_ascii=False,
        )
    )
    return pytest.main([str(ACCEPTANCE_TEST), "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
