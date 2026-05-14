"""Tests for REPL startup auto mode banner (feat-333-M3/R2, M4).

Verifies that:
1. When auto mode is enabled (default), REPL startup prints a brief status banner.
2. When dangerously_skip_permissions=True, REPL startup prints a prominent danger banner.
3. (M4) _load_auto_mode_config_for_repl() reads workspace .nanocode/config.yaml
   and its dangerously_skip_permissions=True overrides the global config (spec A9).

The banner is emitted by print_auto_mode_banner() which is called from _run_repl()
right at startup. We test the function directly to keep tests fast and deterministic.
"""

from __future__ import annotations

import io
import textwrap

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


class TestLoadAutoModeConfigForRepl:
    """Tests for _load_auto_mode_config_for_repl workspace > global priority (feat-333-M4/Issue5)."""

    def test_workspace_config_overrides_global_for_dangerously_skip(
        self, tmp_path: "pytest.FixtureLookupError"
    ) -> None:
        """Workspace .nanocode/config.yaml dangerously_skip_permissions=true must win over global.

        This is the exact scenario from Issue 5: user sets dangerously_skip_permissions in
        workspace config, starts REPL from that directory — banner must show danger warning.
        """
        from pathlib import Path
        from unittest.mock import patch

        from coding_cli.commands import _load_auto_mode_config_for_repl

        # Set up tmp directories for global and workspace configs
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / ".nanocode").mkdir()
        (global_dir / ".nanocode" / "config.yaml").write_text(
            textwrap.dedent("""\
                auto_mode:
                  enabled: true
                  dangerously_skip_permissions: false
            """),
            encoding="utf-8",
        )

        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / ".nanocode").mkdir()
        (workspace_dir / ".nanocode" / "config.yaml").write_text(
            textwrap.dedent("""\
                auto_mode:
                  dangerously_skip_permissions: true
            """),
            encoding="utf-8",
        )

        # Patch Path.home() so global reads from global_dir, cwd() reads from workspace_dir
        with (
            patch("pathlib.Path.home", return_value=global_dir),
            patch("pathlib.Path.cwd", return_value=workspace_dir),
        ):
            config = _load_auto_mode_config_for_repl()

        assert config.dangerously_skip_permissions is True, (
            "workspace config dangerously_skip_permissions=true must override global false"
        )

    def test_global_config_used_when_no_workspace_config(self, tmp_path: "pytest.FixtureLookupError") -> None:
        """When no workspace config exists, global config is the only source."""
        from pathlib import Path
        from unittest.mock import patch

        from coding_cli.commands import _load_auto_mode_config_for_repl

        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / ".nanocode").mkdir()
        (global_dir / ".nanocode" / "config.yaml").write_text(
            textwrap.dedent("""\
                auto_mode:
                  dangerously_skip_permissions: true
            """),
            encoding="utf-8",
        )

        workspace_dir = tmp_path / "workspace_no_config"
        workspace_dir.mkdir()
        # No .nanocode/config.yaml in workspace

        with (
            patch("pathlib.Path.home", return_value=global_dir),
            patch("pathlib.Path.cwd", return_value=workspace_dir),
        ):
            config = _load_auto_mode_config_for_repl()

        assert config.dangerously_skip_permissions is True

    def test_workspace_false_overrides_global_true(self, tmp_path: "pytest.FixtureLookupError") -> None:
        """Workspace dangerously_skip_permissions=false must override global true."""
        from pathlib import Path
        from unittest.mock import patch

        from coding_cli.commands import _load_auto_mode_config_for_repl

        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / ".nanocode").mkdir()
        (global_dir / ".nanocode" / "config.yaml").write_text(
            textwrap.dedent("""\
                auto_mode:
                  dangerously_skip_permissions: true
            """),
            encoding="utf-8",
        )

        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / ".nanocode").mkdir()
        (workspace_dir / ".nanocode" / "config.yaml").write_text(
            textwrap.dedent("""\
                auto_mode:
                  dangerously_skip_permissions: false
            """),
            encoding="utf-8",
        )

        with (
            patch("pathlib.Path.home", return_value=global_dir),
            patch("pathlib.Path.cwd", return_value=workspace_dir),
        ):
            config = _load_auto_mode_config_for_repl()

        assert config.dangerously_skip_permissions is False
