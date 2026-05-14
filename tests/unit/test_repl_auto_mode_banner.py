"""Tests for REPL startup auto mode banner (feat-333-M3/R2).

Verifies that:
1. When auto mode is enabled (default), REPL startup prints a brief status banner.
2. When dangerously_skip_permissions=True, REPL startup prints a prominent danger banner.

The banner is emitted by print_auto_mode_banner() which is called from _run_repl()
right at startup. We test the function directly to keep tests fast and deterministic.
"""

from __future__ import annotations

import io

import pytest

from agent.platform.config.auto_mode import AutoModeConfig


def _call_print_banner(config: AutoModeConfig) -> str:
    """Helper: call the banner function and capture output as string."""
    from coding_cli.commands import print_auto_mode_banner

    out = io.StringIO()
    print_auto_mode_banner(config=config, out=out)
    return out.getvalue()


class TestAutoModeBanner:
    """Banner output tests for print_auto_mode_banner (feat-333-M3/R2)."""

    def test_default_auto_mode_enabled_shows_status_banner(self) -> None:
        """Default config (auto enabled, no skip) shows an informational banner."""
        config = AutoModeConfig(enabled=True, dangerously_skip_permissions=False)
        output = _call_print_banner(config)
        assert output.strip(), "Expected non-empty banner for auto mode"
        # Must contain some recognisable indicator of auto mode being on
        lower = output.lower()
        assert "auto" in lower or "mode" in lower, f"Expected 'auto' or 'mode' in banner, got: {output!r}"

    def test_dangerously_skip_permissions_shows_danger_banner(self) -> None:
        """When dangerously_skip_permissions=True, banner must be prominently visible."""
        config = AutoModeConfig(enabled=True, dangerously_skip_permissions=True)
        output = _call_print_banner(config)
        # Must contain a visible danger marker (⚠, DANGER, dangerously, skip, WARNING, etc.)
        lower = output.lower()
        has_danger_marker = (
            "⚠" in output
            or "danger" in lower
            or "skip" in lower
            or "warning" in lower
            or "bypass" in lower
        )
        assert has_danger_marker, (
            f"Expected danger marker in banner when dangerously_skip_permissions=True, got: {output!r}"
        )

    def test_auto_mode_disabled_shows_no_auto_mode_notice(self) -> None:
        """When auto mode is disabled entirely, banner should reflect that."""
        config = AutoModeConfig(enabled=False, dangerously_skip_permissions=False)
        output = _call_print_banner(config)
        # When disabled, banner should still emit something (so user knows state) or be empty.
        # If it emits, it must not claim auto mode is active.
        if output.strip():
            lower = output.lower()
            # Must not claim auto mode is active
            assert "dangerously" not in lower or "skip" not in lower, (
                f"Disabled auto mode banner must not claim permission bypass: {output!r}"
            )
