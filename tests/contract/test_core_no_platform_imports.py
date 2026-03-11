"""Guard that canonical core packages do not depend on higher-level surfaces."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"
CORE_ROOT = SRC_ROOT / "core"

FORBIDDEN_SNIPPETS = [
    "agent.platform",
    "agent.products",
    "agent.apps",
    "fastapi",
    "starlette",
]


def test_core_packages_do_not_import_platform_product_or_app_surfaces() -> None:
    checked = 0
    for path in CORE_ROOT.rglob("*.py"):
        checked += 1
        source = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            assert snippet not in source, f"{path} imports forbidden higher-level surface: {snippet}"
    assert checked > 0
