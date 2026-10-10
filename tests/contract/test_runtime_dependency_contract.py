"""Product ownership and public DSH dependency boundaries after kernel retirement."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMPORT = re.compile(r"(?:\bfrom\s*|\bimport\s*\(?\s*)['\"]([^'\"]+)['\"]")
ALLOWED = {
    "packages/product-contracts": set(),
    "packages/channels": {"@nano/product-contracts"},
    "packages/personal-assistant": {"@nano/product-contracts", "@nano/channels"},
    "packages/dsh-integration": {"@nano/product-contracts"},
    "apps/im-server": {"@nano/product-contracts"},
    "apps/node": {
        "@nano/product-contracts",
        "@nano/personal-assistant",
        "@nano/channels",
        "@nano/dsh-integration/client",
    },
}


@pytest.mark.parametrize("package", ALLOWED)
def test_product_owns_no_runtime_internals(package: str) -> None:
    """Only the integration package imports DSH; Node sees its process client."""
    for path in (ROOT / package / "src").rglob("*.ts"):
        for specifier in IMPORT.findall(path.read_text()):
            if specifier.startswith("@nano/"):
                assert specifier in ALLOWED[package], (path, specifier)
            if specifier.startswith("@deepseek-ai/"):
                assert package == "packages/dsh-integration", (path, specifier)
            assert not any(
                part in specifier
                for part in ("src/agent", "src/coding_cli", "src/personal_assistant")
            ), (path, specifier)
            if specifier.startswith("."):
                resolved = (path.parent / specifier).resolve()
                assert resolved.is_relative_to(ROOT / package), (path, specifier)


def test_integration_imports_only_declared_public_dsh_exports() -> None:
    """Upgrading DSH must explicitly preserve every imported public export."""
    integration = ROOT / "packages/dsh-integration"
    dependencies = json.loads((integration / "package.json").read_text())[
        "dependencies"
    ]
    for path in (integration / "src").rglob("*.ts"):
        for specifier in IMPORT.findall(path.read_text()):
            if not specifier.startswith("@deepseek-ai/"):
                continue
            parts = specifier.split("/")
            package = "/".join(parts[:2])
            assert package in dependencies, (path, package)
            installed = integration / "node_modules" / package / "package.json"
            assert installed.is_file(), (
                f"Run pnpm install before architecture checks: {package}"
            )
            manifest = json.loads(installed.read_text())
            export = "." if len(parts) == 2 else "./" + "/".join(parts[2:])
            exports = manifest.get("exports", {})
            assert export in exports, (path, specifier, exports)


def test_retired_kernel_and_cli_have_no_shipped_entrypoints() -> None:
    """Historical data and docs cannot silently restore a second execution kernel."""
    for package in ("agent", "coding_cli", "personal_assistant"):
        assert not list((ROOT / "src" / package).rglob("*.py"))
    assert not list((ROOT / "src/IM").glob("*.py"))
    workspace = (ROOT / "pnpm-workspace.yaml").read_text()
    assert "patchedDependencies" not in workspace
    assert not (ROOT / ".pnpmfile.cjs").exists()
