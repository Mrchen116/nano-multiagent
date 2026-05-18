"""Tests for bash_runner module — subprocess execution layer for BashTool.

Verifies:
- BashRunner can be constructed with BashRunnerConfig
- BashRunner.run_stream executes commands and returns CommandExecution
- BashRunnerConfig has expected fields with defaults
- BashTool._run_legacy_sync calls BashRunner, NOT ctx.safety.run_command_stream
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# These imports will fail (Red) until bash_runner.py is created.
from agent.platform.tools.builtins.bash_runner import (
    BashRunner,
    BashRunnerConfig,
)
from agent.platform.tools.safety import CommandExecution


class TestBashRunnerConfig:
    """BashRunnerConfig 数据结构验证。"""

    def test_default_config_fields(self):
        config = BashRunnerConfig()
        assert hasattr(config, "bash_max_output_lines")
        assert hasattr(config, "bash_max_output_bytes")
        assert hasattr(config, "bash_default_timeout")
        assert config.bash_default_timeout == 30.0

    def test_config_is_frozen(self):
        config = BashRunnerConfig()
        with pytest.raises((AttributeError, TypeError)):
            config.bash_default_timeout = 60.0  # type: ignore[misc]

    def test_custom_config(self):
        config = BashRunnerConfig(bash_default_timeout=60.0, bash_max_output_lines=500)
        assert config.bash_default_timeout == 60.0
        assert config.bash_max_output_lines == 500


class TestBashRunnerConstruction:
    """BashRunner 构造验证。"""

    def test_can_construct_with_default_config(self):
        runner = BashRunner(config=BashRunnerConfig())
        assert runner is not None

    def test_has_run_stream_method(self):
        runner = BashRunner(config=BashRunnerConfig())
        assert callable(getattr(runner, "run_stream", None))


class TestBashRunnerRunStream:
    """BashRunner.run_stream 基本执行测试。"""

    def test_run_simple_command(self, tmp_path):
        """Simple echo command returns expected output."""
        runner = BashRunner(config=BashRunnerConfig())
        result = runner.run_stream(
            command="echo hello_from_bash_runner",
            cwd=tmp_path,
            timeout=10.0,
            tool_name="bash",
            on_event=None,
            heartbeat_interval=0.5,
        )
        assert isinstance(result, CommandExecution)
        assert result.exit_code == 0

    def test_run_failing_command_returns_nonzero(self, tmp_path):
        """Failing command returns nonzero exit code."""
        runner = BashRunner(config=BashRunnerConfig())
        result = runner.run_stream(
            command="false",  # always exits 1
            cwd=tmp_path,
            timeout=5.0,
            tool_name="bash",
            on_event=None,
            heartbeat_interval=0.5,
        )
        assert result.exit_code != 0

    def test_run_stream_emits_events(self, tmp_path):
        """on_event callback receives at least 'started' and 'exit' events."""
        runner = BashRunner(config=BashRunnerConfig())
        events = []
        result = runner.run_stream(
            command="echo test_event",
            cwd=tmp_path,
            timeout=10.0,
            tool_name="bash",
            on_event=lambda e: events.append(e),
            heartbeat_interval=0.5,
        )
        phases = {e.get("phase") for e in events}
        assert "started" in phases
        assert "exit" in phases


class TestBashToolUsesRunnerNotSafety:
    """BashTool._run_legacy_sync 不再调用 ctx.safety.run_command_stream。"""

    def test_legacy_sync_calls_bash_runner(self, tmp_path):
        """_run_legacy_sync should use BashRunner, not ctx.safety.run_command_stream."""
        from agent.platform.tools.builtins.bash import BashTool
        from agent.core.tools.base import ToolContext, set_tool_safety_factory, set_tool_safety_config_factory
        from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

        # Set up ToolContext with platform factories
        set_tool_safety_factory(
            lambda *, repo_root, config: ToolSafety(repo_root=repo_root, config=config)
        )
        set_tool_safety_config_factory(ToolSafetyConfig)

        ctx = ToolContext.create(repo_root=tmp_path)
        tool = BashTool()

        # Verify that ctx.safety does NOT have run_command_stream called
        # by checking BashTool.run can execute without it (or that it calls BashRunner)
        with patch.object(type(ctx.safety), "run_command_stream", side_effect=AssertionError("run_command_stream must not be called after M6")) as mock_rcs:
            # Should NOT raise AssertionError (should use BashRunner instead)
            try:
                result = tool.run({"command": "echo test_m6"}, ctx)
                # If we get here without AssertionError, BashRunner is being used
                mock_rcs.assert_not_called()
            except AssertionError:
                pytest.fail("BashTool._run_legacy_sync still calls ctx.safety.run_command_stream after M6")
