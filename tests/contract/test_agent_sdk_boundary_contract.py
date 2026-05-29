"""Boundary guard: products must only import agent.sdk (refactor-387).

This file establishes the guard framework for the target architecture where
coding_cli and personal_assistant may only import from agent.sdk — not from
agent.core, agent.platform, or agent.products internals.

Phase status (refactor-387):
- M1: Framework established; agent.sdk has no reverse dependencies (verified).
      Known pre-existing violations in coding_cli and personal_assistant are
      explicitly enumerated (kernel_app.py etc.) and will be fixed in M2/M3.
      The guard for those files is active but PASSES because the violations
      are expected at this phase.
- M4: All violations resolved; full strict guard becomes active.

Architecture invariant enforced here:
  agent.sdk → agent.core + agent.platform + agent.products  (correct, downward)
  agent.core / agent.platform / agent.products ↛ agent.sdk  (no upward dep)
  coding_cli / personal_assistant → only agent.sdk          (target, M2/M3/M4)
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
AGENT_SDK_ROOT = SRC_ROOT / "agent" / "sdk"


# Files in products that have KNOWN violations in M1 (will be fixed in M2/M3).
# Each entry documents what the violation is and which milestone will fix it.
# Format: "relative/path/from/src" → ["forbidden_prefix", ...]
_M2_M3_KNOWN_VIOLATIONS: dict[str, list[str]] = {
    # M2: coding_cli will be rewritten to import only agent.sdk
    "coding_cli/kernel_app.py": ["agent.core", "agent.platform", "agent.products"],
    # M3: personal_assistant will be rewritten to import only agent.sdk
    "personal_assistant/kernel_app.py": ["agent.core", "agent.platform", "agent.products"],
    "personal_assistant/main.py": ["agent.core"],
    "personal_assistant/config/local_store.py": ["agent.core"],
    "personal_assistant/reporter/upstream_reporter.py": ["agent.core", "agent.platform", "agent.products"],
    "personal_assistant/gateway/inbound_pipeline.py": ["agent.core", "agent.platform"],
    "personal_assistant/client/kernel_api_client.py": ["agent.core", "agent.platform"],
}

# Agent-internal prefixes that products must NOT import directly in the target arch.
_FORBIDDEN_INTERNAL_PREFIXES = [
    "agent.core",
    "agent.platform",
    "agent.products",
]


def _collect_product_agent_imports(package_root: Path) -> list[tuple[str, int, str]]:
    """Return (rel_path, lineno, import_str) for each forbidden agent.* import."""
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
                    if any(m.startswith(p) for p in _FORBIDDEN_INTERNAL_PREFIXES):
                        violations.append((rel, node.lineno, m))
                continue
            if module and any(module.startswith(p) for p in _FORBIDDEN_INTERNAL_PREFIXES):
                # Check if this is in the known M2/M3 violations whitelist.
                if rel not in _M2_M3_KNOWN_VIOLATIONS:
                    violations.append((rel, node.lineno, module))
                elif not any(module.startswith(v) for v in _M2_M3_KNOWN_VIOLATIONS[rel]):
                    # The file is known to violate, but this specific prefix is NEW.
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


def test_no_new_unexpected_product_agent_internal_imports() -> None:
    """Products must not introduce NEW forbidden agent.core/platform imports beyond M2/M3 whitelist.

    In M1, known violations are whitelisted (M2/M3 will fix them).
    Any import NOT in the whitelist will fail immediately — preventing scope creep.
    """
    coding_cli_root = SRC_ROOT / "coding_cli"
    pa_root = SRC_ROOT / "personal_assistant"

    all_violations: list[tuple[str, int, str]] = []
    for root in (coding_cli_root, pa_root):
        if root.exists():
            all_violations.extend(_collect_product_agent_imports(root))

    if all_violations:
        lines = [f"  {rel}:{lineno}: imports {module!r}" for rel, lineno, module in all_violations]
        raise AssertionError(
            "Product files have UNEXPECTED new agent internal imports "
            "(not in M2/M3 whitelist — add to _M2_M3_KNOWN_VIOLATIONS if legitimately deferred):\n"
            + "\n".join(lines)
        )


def test_agent_sdk_exposes_build_kernel_and_kernel() -> None:
    """agent.sdk must export build_kernel and Kernel as its public API."""
    from agent.sdk import Kernel, build_kernel  # noqa: PLC0415

    assert callable(build_kernel)
    assert isinstance(Kernel, type)
