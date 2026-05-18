"""Background command execution — M6 migration note.

After bugfix-355-M6: ToolSafety.start_command_background has been removed.
Background command execution is now handled by ShellRunner in:
  agent.platform.background_tasks.shell_runner.ShellRunner

Coverage for ShellRunner background execution lives in:
  tests/unit/agent/background_tasks/test_platform_adapters.py
  - test_shell_runner_completes_with_exit_0
  - test_shell_runner_fails_on_nonzero_exit
  - test_shell_runner_stop_terminates_process
  - test_shell_runner_output_ready_when_complete_callback_fires
  - test_shell_runner_timeout_kills_process

Removal of start_command_background from ToolSafety is verified in:
  tests/unit/agent/platform/tools/test_safety.py::TestToolSafetyM6MethodCleanup
  - test_start_command_background_removed

This file is kept as a tombstone to prevent silent regressions where
someone might re-add background methods to ToolSafety.
"""

from pathlib import Path

from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


def test_start_command_background_removed_from_tool_safety() -> None:
    """start_command_background must not exist on ToolSafety after M6."""
    safety = ToolSafety(repo_root=Path("/tmp"), config=ToolSafetyConfig())
    assert not hasattr(safety, "start_command_background"), (
        "start_command_background was removed from ToolSafety in M6 (bugfix-355). "
        "Background execution is now in ShellRunner. "
        "See tests/unit/agent/background_tasks/test_platform_adapters.py for coverage."
    )


def test_run_command_stream_removed_from_tool_safety() -> None:
    """run_command_stream must not exist on ToolSafety after M6."""
    safety = ToolSafety(repo_root=Path("/tmp"), config=ToolSafetyConfig())
    assert not hasattr(safety, "run_command_stream"), (
        "run_command_stream was removed from ToolSafety in M6 (bugfix-355). "
        "Foreground execution is now in BashRunner. "
        "See tests/unit/agent/platform/tools/builtins/test_bash_runner.py for coverage."
    )
