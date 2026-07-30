#!/usr/bin/env python3
"""Commenting contract checks for milestone M29."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "nano_multiagent"
TARGET_DIRS = ("tools", "hooks", "skills", "session")

# These marker strings assert that critical "why/constraint/boundary/cost"
# notes exist for safety policy, hook fail-open isolation, and session persistence.
REQUIRED_MARKERS: dict[str, tuple[str, ...]] = {
    "src/nano_multiagent/tools/safety.py": (
        "SECURITY BOUNDARY:",
        "POLICY TRADE-OFF:",
    ),
    "src/nano_multiagent/tools/registry.py": ("FAIL-OPEN GUARANTEE:",),
    "src/nano_multiagent/hooks/runner.py": ("DISPATCH ISOLATION:",),
    "src/nano_multiagent/session/stores/base.py": ("STORE BOUNDARY:",),
    "src/nano_multiagent/session/serializers.py": ("PERSISTENCE PROTOCOL:",),
}


def iter_target_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for area in TARGET_DIRS:
        files.extend(sorted((SRC_ROOT / area).rglob("*.py")))
    return tuple(files)


def missing_public_docstrings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    missing: list[str] = []
    module_doc = ast.get_docstring(tree)
    if not module_doc:
        missing.append("module")

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if not ast.get_docstring(node):
                missing.append(node.name)
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if child.name.startswith("_"):
                            continue
                        if not ast.get_docstring(child):
                            missing.append(f"{node.name}.{child.name}")
    return missing


def missing_markers() -> list[str]:
    missing: list[str] = []
    for relative, markers in REQUIRED_MARKERS.items():
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                missing.append(f"{relative} -> {marker}")
    return missing


def main() -> int:
    failed = False
    for path in iter_target_files():
        misses = missing_public_docstrings(path)
        if misses:
            failed = True
            relative = path.relative_to(REPO_ROOT)
            print(f"[MISSING_DOCSTRING] {relative}: {', '.join(misses)}")

    markers = missing_markers()
    for item in markers:
        failed = True
        print(f"[MISSING_MARKER] {item}")

    if failed:
        return 1
    print("M29 commenting contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
