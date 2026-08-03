"""Non-prompt archive artifacts contracts."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_pr_templates_use_stable_absolute_blob_links() -> None:
    template = _read(
        ".claude/skills/change-orchestrator/references/pr-body-templates.md"
    )

    assert "](docs/changes/" not in template
    assert template.count("/blob/<pr_head_sha>/docs/changes/archive/") == 5
