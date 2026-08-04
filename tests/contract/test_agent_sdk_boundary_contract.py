"""Guard the public ``agent.sdk`` dependency boundary."""

from __future__ import annotations

from pathlib import Path

from tests.contract.import_rules import (
    ImportReference,
    absolute_imports,
    forbidden_imports,
    matches_prefix,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
AGENT_SDK_ROOT = SRC_ROOT / "agent" / "sdk"


def _collect_product_agent_imports(package_root: Path) -> list[ImportReference]:
    """Return product imports that bypass the agent.sdk root surface."""
    return [
        reference
        for reference in absolute_imports(package_root)
        if matches_prefix(reference.module, "agent") and reference.module != "agent.sdk"
    ]


def _render(reference: ImportReference) -> str:
    return (
        f"{reference.path.relative_to(SRC_ROOT)}:{reference.line}: "
        f"imports {reference.module!r}"
    )


def test_agent_sdk_has_no_upward_dependency_on_products() -> None:
    """agent.sdk must not import coding_cli, personal_assistant, or IM.

    This is the most critical invariant: the public surface cannot depend on
    the products that consume it (that would be a circular dependency).
    """
    violations = forbidden_imports(
        AGENT_SDK_ROOT,
        ("coding_cli", "personal_assistant", "IM"),
    )
    assert not violations, "agent.sdk imports product packages:\n  " + "\n  ".join(
        _render(reference) for reference in violations
    )


def test_products_import_only_agent_sdk_root() -> None:
    """Products must import the kernel only through the agent.sdk root surface."""
    coding_cli_root = SRC_ROOT / "coding_cli"
    pa_root = SRC_ROOT / "personal_assistant"

    all_violations: list[ImportReference] = []
    for root in (coding_cli_root, pa_root):
        all_violations.extend(_collect_product_agent_imports(root))

    if all_violations:
        raise AssertionError(
            "Product files bypass the agent.sdk root surface:\n  "
            + "\n  ".join(_render(reference) for reference in all_violations)
        )


def test_agent_sdk_exposes_build_kernel_and_kernel() -> None:
    """agent.sdk must export build_kernel and Kernel as its public API."""
    from agent.sdk import Kernel, build_kernel  # noqa: PLC0415

    assert callable(build_kernel)
    assert isinstance(Kernel, type)
