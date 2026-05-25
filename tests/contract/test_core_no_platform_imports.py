"""Guard that canonical core packages do not depend on higher-level surfaces.

Only import statements are checked (not docstrings or comments) to avoid
false positives when a module's documentation mentions a higher-level surface
by name without actually importing it.
"""

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"
CORE_ROOT = SRC_ROOT / "core"

# Match only actual import lines to avoid false positives from docstrings.
_IMPORT_LINE_RE = re.compile(r"^\s*(?:from|import)\s+", re.MULTILINE)

FORBIDDEN_PREFIXES = [
    "agent.platform",
    "agent.products",
    "agent.apps",
    "fastapi",
    "starlette",
]


@pytest.mark.xfail(
    reason=(
        "agent.core.llm.factory imports agent.platform.llm.providers (concrete LLM clients), "
        "violating the core-does-not-depend-on-platform constraint; tracked in #40"
    ),
    strict=True,
)
def test_core_packages_do_not_import_platform_product_or_app_surfaces() -> None:
    checked = 0
    for path in CORE_ROOT.rglob("*.py"):
        checked += 1
        source = path.read_text(encoding="utf-8")
        # Extract only import statement lines to skip docstrings and comments.
        import_lines = "\n".join(
            line for line in source.splitlines() if _IMPORT_LINE_RE.match(line)
        )
        for prefix in FORBIDDEN_PREFIXES:
            assert prefix not in import_lines, (
                f"{path} imports forbidden higher-level surface: {prefix}"
            )
    assert checked > 0
