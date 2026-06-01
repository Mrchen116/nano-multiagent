"""Tests for ToolSafety after bugfix-355 resolve_read_path removal (M1) and
bash_* field/method migration (M6).

Verifies:
- resolve_read_path method no longer exists (deleted, not just modified) [M1]
- normalize_path still works (path expansion, cwd join, resolve) [M1]
- is_path_in_workspace still exists (needed by write tools) [M1]
- ReadTool can read files outside workspace (via normalize_path only) [M1]
- ToolSafetyConfig no longer has bash_* fields [M6]
- ToolSafety no longer has check_command_policy / enforce_command_policy / run_command_stream [M6]
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig
from agent.core.errors import ToolError


class TestResolveReadPathRemoved:
    def test_resolve_read_path_does_not_exist(self):
        """resolve_read_path must be deleted — no longer in ToolSafety (Anchor E)."""
        safety = ToolSafety(
            repo_root=Path("/workspace"),
            config=ToolSafetyConfig(),
        )
        assert not hasattr(safety, "resolve_read_path"), (
            "resolve_read_path must be deleted from ToolSafety (bugfix-355 Anchor E)"
        )

    def test_read_allowed_roots_does_not_exist(self):
        """_read_allowed_roots private helper must also be deleted."""
        safety = ToolSafety(
            repo_root=Path("/workspace"),
            config=ToolSafetyConfig(),
        )
        assert not hasattr(safety, "_read_allowed_roots"), (
            "_read_allowed_roots must be deleted along with resolve_read_path"
        )


class TestNormalizePathPreserved:
    def test_normalize_absolute_path(self):
        """normalize_path resolves absolute paths without boundary check."""
        safety = ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())
        # /tmp is outside /workspace — should succeed (no boundary check)
        result = safety.normalize_path("/tmp/test_file.txt", cwd=Path("/workspace"))
        # Use resolved path for comparison (macOS /tmp → /private/tmp symlink)
        assert result == Path("/tmp/test_file.txt").resolve()

    def test_normalize_relative_path_joins_cwd(self):
        """normalize_path joins relative paths with cwd."""
        safety = ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())
        result = safety.normalize_path("src/main.py", cwd=Path("/workspace"))
        assert result == Path("/workspace/src/main.py")

    def test_normalize_tilde_path(self):
        """normalize_path expands ~ paths."""
        safety = ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())
        result = safety.normalize_path("~/some/file.txt", cwd=Path("/workspace"))
        assert not str(result).startswith("~"), "normalize_path must expand ~"

    def test_normalize_path_outside_workspace_allowed(self):
        """normalize_path must succeed for paths outside workspace — no raise."""
        safety = ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())
        # This should not raise ToolError
        result = safety.normalize_path("/etc/hosts", cwd=Path("/workspace"))
        # Use resolved for comparison (macOS may have symlinks like /etc → /private/etc)
        assert result == Path("/etc/hosts").resolve()


class TestIsPathInWorkspacePreserved:
    def test_is_path_in_workspace_inside(self):
        """is_path_in_workspace returns True for paths inside workspace."""
        safety = ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())
        assert safety.is_path_in_workspace(Path("/workspace/src/main.py")) is True

    def test_is_path_in_workspace_outside(self):
        """is_path_in_workspace returns False for paths outside workspace."""
        safety = ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())
        assert safety.is_path_in_workspace(Path("/tmp/file.txt")) is False


class TestReadToolUsesNormalizePathOnly:
    """Verify ReadTool uses normalize_path not resolve_read_path after Anchor E."""

    def test_read_tool_reads_outside_workspace(self, tmp_path):
        """ReadTool must successfully read files outside the workspace root."""
        import tempfile, os
        from agent.platform.tools.builtins.read import ReadTool
        from agent.core.tools.base import ToolContext

        # Create a temp file outside any workspace
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        test_file = outside_dir / "README.md"
        test_file.write_text("Hello from outside!", encoding="utf-8")

        # Use a different dir as workspace
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Register factories needed by ToolContext.create
        from agent.platform.tools import safety as safety_module
        from agent.core.tools import base as base_module
        from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

        base_module.set_tool_safety_factory(
            lambda *, repo_root, config: ToolSafety(repo_root=repo_root, config=config)
        )
        base_module.set_tool_safety_config_factory(ToolSafetyConfig)

        ctx = ToolContext.create(repo_root=workspace_dir)

        tool = ReadTool()
        # Reading a file outside workspace should succeed (no ToolError for "path is outside repo sandbox")
        result = tool.run({"path": str(test_file)}, ctx)
        assert "content" in result
        # Content should have the text
        serialized = tool.serialize_result(result)
        assert "Hello from outside!" in serialized


# ---------------------------------------------------------------------------
# M6: ToolSafetyConfig and ToolSafety cleanup assertions
# ---------------------------------------------------------------------------


class TestToolSafetyConfigM6Cleanup:
    """After M6, ToolSafetyConfig must NOT have bash_* fields — they live in bash_policy.py."""

    def test_config_has_no_bash_allowed_prefixes(self):
        """bash_allowed_prefixes removed from ToolSafetyConfig (moved to bash_policy.py)."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_allowed_prefixes"), (
            "bash_allowed_prefixes must be deleted from ToolSafetyConfig (M6 migration)"
        )

    def test_config_has_no_bash_allowed_commands(self):
        """bash_allowed_commands removed from ToolSafetyConfig."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_allowed_commands"), (
            "bash_allowed_commands must be deleted from ToolSafetyConfig (M6)"
        )

    def test_config_has_no_bash_blocked_commands(self):
        """bash_blocked_commands removed from ToolSafetyConfig."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_blocked_commands"), (
            "bash_blocked_commands must be deleted from ToolSafetyConfig (M6)"
        )

    def test_config_has_no_bash_blocked_fragments(self):
        """bash_blocked_fragments removed from ToolSafetyConfig."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_blocked_fragments"), (
            "bash_blocked_fragments must be deleted from ToolSafetyConfig (M6)"
        )

    def test_config_has_no_bash_max_output_lines(self):
        """bash_max_output_lines removed (moved to BashRunnerConfig)."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_max_output_lines"), (
            "bash_max_output_lines must be deleted from ToolSafetyConfig (M6)"
        )

    def test_config_has_no_bash_max_output_bytes(self):
        """bash_max_output_bytes removed (moved to BashRunnerConfig)."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_max_output_bytes"), (
            "bash_max_output_bytes must be deleted from ToolSafetyConfig (M6)"
        )

    def test_config_has_no_bash_default_timeout(self):
        """bash_default_timeout removed (moved to BashRunnerConfig)."""
        config = ToolSafetyConfig()
        assert not hasattr(config, "bash_default_timeout"), (
            "bash_default_timeout must be deleted from ToolSafetyConfig (M6)"
        )

    def test_config_retains_read_max_bytes(self):
        """read_max_bytes must still exist in ToolSafetyConfig."""
        config = ToolSafetyConfig()
        assert hasattr(config, "read_max_bytes"), (
            "read_max_bytes must remain in ToolSafetyConfig"
        )

    def test_config_retains_read_max_lines(self):
        """read_max_lines must still exist in ToolSafetyConfig."""
        config = ToolSafetyConfig()
        assert hasattr(config, "read_max_lines"), (
            "read_max_lines must remain in ToolSafetyConfig"
        )


class TestToolSafetyM6MethodCleanup:
    """After M6, ToolSafety must NOT have bash-specific methods."""

    def _make_safety(self):
        return ToolSafety(repo_root=Path("/workspace"), config=ToolSafetyConfig())

    def test_check_command_policy_removed(self):
        """check_command_policy must be deleted from ToolSafety (moved to bash_policy.py)."""
        safety = self._make_safety()
        assert not hasattr(safety, "check_command_policy"), (
            "check_command_policy must be deleted from ToolSafety (M6)"
        )

    def test_enforce_command_policy_removed(self):
        """enforce_command_policy must be deleted from ToolSafety (moved to bash_policy.py)."""
        safety = self._make_safety()
        assert not hasattr(safety, "enforce_command_policy"), (
            "enforce_command_policy must be deleted from ToolSafety (M6)"
        )

    def test_run_command_stream_removed(self):
        """run_command_stream must be deleted from ToolSafety (moved to bash_runner.py)."""
        safety = self._make_safety()
        assert not hasattr(safety, "run_command_stream"), (
            "run_command_stream must be deleted from ToolSafety (M6)"
        )

    def test_run_command_removed(self):
        """run_command convenience wrapper must be deleted from ToolSafety (M6)."""
        safety = self._make_safety()
        assert not hasattr(safety, "run_command"), (
            "run_command must be deleted from ToolSafety (M6)"
        )

    def test_start_command_background_removed(self):
        """start_command_background must be deleted from ToolSafety (M6)."""
        safety = self._make_safety()
        assert not hasattr(safety, "start_command_background"), (
            "start_command_background must be deleted from ToolSafety (M6)"
        )
