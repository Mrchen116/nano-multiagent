"""Guard that platform packages do not depend on the SDK composition surface."""

from pathlib import Path

from tests.contract.import_rules import forbidden_imports

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"
PLATFORM_ROOT = SRC_ROOT / "platform"

FORBIDDEN_PREFIXES = ["agent.sdk"]


def test_platform_packages_do_not_import_sdk_surface() -> None:
    violations = forbidden_imports(PLATFORM_ROOT, FORBIDDEN_PREFIXES)
    assert not violations, "platform imports SDK surface:\n  " + "\n  ".join(
        f"{item.path.relative_to(PROJECT_ROOT)}:{item.line}: {item.module}"
        for item in violations
    )
