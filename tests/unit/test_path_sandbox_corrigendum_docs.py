"""Tests verifying refactor-353 documents have corrigendum annotations (bugfix-355 D6).

These tests encode the documentation contract — the corrigendum must be present
so future readers understand the corrected CC behavior.
"""

from pathlib import Path
import pytest


DOCS_BASE = Path(__file__).parent.parent.parent / "docs" / "changes"
REFACTOR_353_DIR = DOCS_BASE / "refactor-353-unify-path-sandbox"


class TestRefactor353Corrigendum:
    def test_spec_md_exists(self):
        """refactor-353/spec.md must exist."""
        assert (REFACTOR_353_DIR / "spec.md").exists(), (
            "refactor-353/spec.md not found"
        )

    def test_design_md_exists(self):
        """refactor-353/design.md must exist."""
        assert (REFACTOR_353_DIR / "design.md").exists(), (
            "refactor-353/design.md not found"
        )

    def test_spec_md_has_corrigendum(self):
        """spec.md Q1 must have Corrigendum annotation from bugfix-355."""
        content = (REFACTOR_353_DIR / "spec.md").read_text(encoding="utf-8")
        assert "Corrigendum" in content, (
            "spec.md must have Corrigendum block (bugfix-355 D6)"
        )
        assert "bugfix-355" in content, (
            "spec.md Corrigendum must reference bugfix-355"
        )

    def test_spec_md_corrigendum_describes_cc_behavior(self):
        """spec.md corrigendum must describe actual CC Read behavior per mode."""
        content = (REFACTOR_353_DIR / "spec.md").read_text(encoding="utf-8")
        # Must mention the corrected CC mode behaviors
        assert "auto" in content.lower() or "SAFE_YOLO" in content or "safe-allowlist" in content.lower(), (
            "spec.md corrigendum must describe CC auto mode Read behavior"
        )
        assert "bypass" in content.lower() or "bypassPermissions" in content, (
            "spec.md corrigendum must describe CC bypass mode behavior"
        )

    def test_design_md_has_corrigendum(self):
        """design.md decision 2 must have Corrigendum annotation from bugfix-355."""
        content = (REFACTOR_353_DIR / "design.md").read_text(encoding="utf-8")
        assert "Corrigendum" in content, (
            "design.md must have Corrigendum block (bugfix-355 D6)"
        )
        assert "bugfix-355" in content, (
            "design.md Corrigendum must reference bugfix-355"
        )

    def test_spec_md_has_changelog_entry(self):
        """spec.md Changelog must have a bugfix-355 entry."""
        content = (REFACTOR_353_DIR / "spec.md").read_text(encoding="utf-8")
        assert "2026-05-16" in content and "bugfix-355" in content, (
            "spec.md Changelog must have 2026-05-16 bugfix-355 entry"
        )

    def test_design_md_has_changelog_entry(self):
        """design.md Changelog must have a bugfix-355 entry."""
        content = (REFACTOR_353_DIR / "design.md").read_text(encoding="utf-8")
        assert "2026-05-16" in content and "bugfix-355" in content, (
            "design.md Changelog must have 2026-05-16 bugfix-355 entry"
        )
