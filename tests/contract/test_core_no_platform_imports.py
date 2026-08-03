"""Guard that core packages do not depend on higher-level surfaces."""

from pathlib import Path

from tests.contract.import_rules import forbidden_imports

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"
CORE_ROOT = SRC_ROOT / "core"

FORBIDDEN_PREFIXES = [
    "agent.sdk",
    "agent.platform",
    "fastapi",
    "starlette",
]


def test_core_packages_do_not_import_higher_level_surfaces() -> None:
    violations = forbidden_imports(CORE_ROOT, FORBIDDEN_PREFIXES)
    assert not violations, "core imports higher-level surfaces:\n  " + "\n  ".join(
        f"{item.path.relative_to(PROJECT_ROOT)}:{item.line}: {item.module}"
        for item in violations
    )
