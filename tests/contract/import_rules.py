"""Parse production imports for architecture boundary contracts."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ImportReference:
    """Describe one absolute import in a Python source tree."""

    path: Path
    line: int
    module: str


def absolute_imports(package_root: Path) -> list[ImportReference]:
    """Return absolute imports declared below ``package_root``."""
    references: list[ImportReference] = []
    for source_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                references.extend(
                    ImportReference(source_path, node.lineno, alias.name)
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                references.append(
                    ImportReference(source_path, node.lineno, node.module)
                )
    return references


def matches_prefix(module: str, prefix: str) -> bool:
    """Return whether ``module`` is ``prefix`` or one of its children."""
    return module == prefix or module.startswith(f"{prefix}.")


def forbidden_imports(
    package_root: Path,
    forbidden_prefixes: Iterable[str],
) -> list[ImportReference]:
    """Return imports below ``package_root`` matching forbidden module roots."""
    prefixes = tuple(forbidden_prefixes)
    return [
        reference
        for reference in absolute_imports(package_root)
        if any(matches_prefix(reference.module, prefix) for prefix in prefixes)
    ]
