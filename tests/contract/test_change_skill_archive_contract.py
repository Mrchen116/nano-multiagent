"""Contracts for rendered change-workflow artifacts."""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_pr_templates_use_stable_absolute_blob_links() -> None:
    template = _read(
        ".claude/skills/change-orchestrator/references/pr-body-templates.md"
    )

    link_targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", template)
    change_links = [target for target in link_targets if "docs/changes/" in target]

    assert change_links
    assert all(
        target.startswith(
            "<repo_url>/blob/<pr_head_sha>/docs/changes/archive/<unit_dir>/"
        )
        for target in change_links
    )
