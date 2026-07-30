"""Boundary guard: products must only import agent.sdk (refactor-387).

This file establishes the guard framework for the target architecture where
coding_cli and personal_assistant may only import from agent.sdk — not from
agent.core or agent.platform internals. The retired agent.products namespace
also remains forbidden to prevent the old layer from being reintroduced.

Phase status (refactor-387):
- M1: Framework established; agent.sdk has no reverse dependencies (verified).
- M2/M3: coding_cli and personal_assistant migrated to agent.sdk; dead files kept.
- M4: All violations resolved; dead files deleted; full strict guard active (Closes #39).

Architecture invariant enforced here:
  agent.sdk → agent.core + agent.platform           (correct, downward)
  agent.core / agent.platform ↛ agent.sdk           (no upward dependency)
  coding_cli / personal_assistant → only agent.sdk  (target, M2/M3/M4)
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
AGENT_SDK_ROOT = SRC_ROOT / "agent" / "sdk"


def _is_forbidden_product_agent_import(module: str) -> bool:
    """Return whether a product import bypasses the agent.sdk root surface."""
    if module == "agent.sdk":
        return False
    return module == "agent" or module.startswith("agent.")


def _collect_product_agent_imports(package_root: Path) -> list[tuple[str, int, str]]:
    """Return product imports that bypass the agent.sdk root surface."""
    violations: list[tuple[str, int, str]] = []
    for py_file in sorted(package_root.rglob("*.py")):
        rel = str(py_file.relative_to(SRC_ROOT))
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    m = alias.name
                    if _is_forbidden_product_agent_import(m):
                        violations.append((rel, node.lineno, m))
                continue
            if module and _is_forbidden_product_agent_import(module):
                violations.append((rel, node.lineno, module))
    return violations


def test_agent_sdk_has_no_upward_dependency_on_products() -> None:
    """agent.sdk must not import coding_cli, personal_assistant, or IM.

    This is the most critical invariant: the public surface cannot depend on
    the products that consume it (that would be a circular dependency).
    """
    forbidden = ["coding_cli", "personal_assistant", "IM"]
    for py_file in sorted(AGENT_SDK_ROOT.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for bad in forbidden:
                        assert not alias.name.startswith(bad), (
                            f"agent.sdk imports product package {alias.name!r} "
                            f"in {py_file.relative_to(SRC_ROOT)}:{node.lineno}"
                        )
                continue
            if module:
                for bad in forbidden:
                    assert not module.startswith(bad), (
                        f"agent.sdk imports product package {module!r} "
                        f"in {py_file.relative_to(SRC_ROOT)}:{node.lineno}"
                    )


def test_products_import_only_agent_sdk_root() -> None:
    """Products must import the kernel only through the agent.sdk root surface."""
    coding_cli_root = SRC_ROOT / "coding_cli"
    pa_root = SRC_ROOT / "personal_assistant"

    all_violations: list[tuple[str, int, str]] = []
    for root in (coding_cli_root, pa_root):
        if root.exists():
            all_violations.extend(_collect_product_agent_imports(root))

    if all_violations:
        lines = [
            f"  {rel}:{lineno}: imports {module!r}"
            for rel, lineno, module in all_violations
        ]
        raise AssertionError(
            "Product files bypass the agent.sdk root surface:\n"
            + "\n".join(lines)
        )


def test_agent_sdk_exposes_build_kernel_and_kernel() -> None:
    """agent.sdk must export build_kernel and Kernel as its public API."""
    from agent.sdk import Kernel, build_kernel  # noqa: PLC0415

    assert callable(build_kernel)
    assert isinstance(Kernel, type)
