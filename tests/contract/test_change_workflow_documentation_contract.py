"""Contract tests for the documented change-* lifecycle invariants."""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).parent.parent.parent


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def test_spec_review_remains_optional() -> None:
    workflow = _read("docs/development/change-workflow.md")
    storage = _read("docs/changes/README.md")

    workflow_mentions = [
        line for line in workflow.splitlines() if "`change-spec-reviewer`" in line
    ]
    storage_mentions = [
        line for line in storage.splitlines() if "`spec-review.md`" in line
    ]
    assert any("可选" in line or "按需" in line for line in workflow_mentions)
    assert any("可选" in line or "按需" in line for line in storage_mentions)
