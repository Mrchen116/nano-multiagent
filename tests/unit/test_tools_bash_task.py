"""Unit tests for BashTool: execution, permissions, output handling, serialize_result."""

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.background_tasks.shell_runner import ShellRunner
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.safety import ToolSafety
from agent.platform.tools.safety import ToolSafetyConfig
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def _bash(tmp_path: Path) -> BashTool:
    """A BashTool on the production wired path (ShellRunner foreground engine).

    bugfix-417-M4 (decision 8): the dead no-wiring path (_run_legacy_sync) was deleted.
    Production always wires bash via build_kernel, so the unit contracts now run the
    real ShellRunner engine. ``runs_registry=None`` skips background notification wiring
    (irrelevant to foreground bash) while still providing a real ShellRunner.
    """
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=None)
    assert isinstance(wiring.bash_runner, ShellRunner)
    return BashTool(wiring=wiring)


# ---------------------------------------------------------------------------
# BashTool execution
# ---------------------------------------------------------------------------


def test_bash_reports_non_zero_exit(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        _bash(tmp_path).run({"command": 'python3 -c "import sys;sys.exit(7)"'}, ctx)

    assert str(exc_info.value).endswith("Command exited with code 7")
    assert exc_info.value.details["exitCode"] == 7
    assert exc_info.value.details["tool_name"] == "bash"
    assert "content" in exc_info.value.details


def test_bash_handles_timeout(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(
        ToolError, match="Command timed out after 0.3 seconds"
    ) as exc_info:
        _bash(tmp_path).run(
            {
                "command": (
                    'python3 -c "import time; '
                    "print('before-timeout', flush=True); "
                    'time.sleep(5)"'
                ),
                "timeout": 0.3,
            },
            ctx,
        )
    assert exc_info.value.details["timedOut"] is True
    assert exc_info.value.details["timeout"] == 0.3
    assert exc_info.value.details["tool_name"] == "bash"
    assert isinstance(exc_info.value.details["content"], str)
    # bugfix-417-M3 R4 (decision 5): a tool's own deadline classifies as tool_timeout
    # ("执行超时"), distinct from a watchdog liveness stall ("已中断"). reason_code rides
    # the ToolError details → ToolResult → tool_end badge.
    assert exc_info.value.details["reason_code"] == "tool_timeout"


def test_bash_rejects_disallowed_command_via_check_permissions(tmp_path: Path) -> None:
    """After M6 (D10 single-point principle), policy is checked in check_permissions,
    not in BashTool.run. This test validates check_permissions returns 'deny' for
    blocked commands and 'passthrough' for review-class commands.

    BashTool.run no longer raises ToolError for unlisted commands; that decision
    is now made by the auto_mode_gate hook which calls check_permissions first.
    """
    from agent.platform.permissions.broker import PermissionDecision

    ctx = _context(tmp_path)
    tool = BashTool()

    # Blocked command → deny from check_permissions
    result = tool.check_permissions({"command": "reboot"}, ctx)
    assert isinstance(result, PermissionDecision)
    assert result.behavior == "deny"

    # Fork-bomb → deny
    result = tool.check_permissions({"command": ":(){:|:&};:"}, ctx)
    assert result.behavior == "deny"

    # Review command (rm -rf) → passthrough (classifier decides)
    result = tool.check_permissions({"command": "rm -rf /tmp/forbidden"}, ctx)
    assert result.behavior == "passthrough"


def test_bash_small_output_not_truncated(tmp_path: Path) -> None:
    # 小输出原样返回，不在 bash 工具体内截断。
    ctx = _context(tmp_path)

    result = _bash(tmp_path).run(
        {"command": "python3 -c \"[print(f'line-{i}') for i in range(10)]\""},
        ctx,
    )

    assert result["truncated"] is False
    assert "line-0" in result["stdout"]
    assert "line-9" in result["stdout"]


# bugfix-417-M4 (decision 8): the bash-tool-body 1MB hard limit (truncated=True +
# fullOutputPath) lived ONLY on the deleted dead path (_run_legacy_sync). The production
# wired path returns raw output and relies on the downstream result-budget compressor
# (covered by tests/unit/test_tool_result_budget.py), so no bash-level hard-limit test
# remains here.


def test_bash_without_timeout_runs_to_completion(tmp_path: Path) -> None:
    """A bash command with no explicit timeout runs to completion — no default deadline
    is injected that would prematurely kill a normal command (bugfix-417-M4: verified on
    the production wired ShellRunner path, which passes timeout=None straight through to
    Popen.wait, so a finite command always completes)."""
    ctx = _context(tmp_path)

    result = _bash(tmp_path).run({"command": "python3 -c \"print('ok')\""}, ctx)

    assert result["stdout"] == "ok"
    assert result["exitCode"] == 0


def test_bash_success_merges_stdout_and_stderr_into_stdout(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    result = BashTool().run(
        {
            "command": (
                'python -c "import sys; '
                "print('out-1'); "
                "sys.stderr.write('err-1\\\\n'); "
                "print('out-2')\""
            )
        },
        ctx,
    )

    assert result["stdout"]
    assert "out-1" in result["stdout"]
    assert "err-1" in result["stdout"]
    assert "out-2" in result["stdout"]
    assert "stderr" in result


# bugfix-417-M4 (decision 8): the bash-tool "Command aborted" ToolError
# (details={"aborted": True}) was a dead-path (_run_legacy_sync) concept that caught a
# synchronous KeyboardInterrupt inside run_stream. The production wired path has no such
# branch — interruption now flows through kernel.cancel → task cancel (M1, run-level
# stop_reason="aborted"), not a bash-tool ToolError. No bash-level aborted contract test
# remains here.


# ---------------------------------------------------------------------------
# BashTool serialize_result
# ---------------------------------------------------------------------------


def test_bash_serialize_result_success() -> None:
    tool = BashTool()
    output = {"stdout": "line-1\nline-2", "exitCode": 0, "truncated": False}
    result = tool.serialize_result(output)
    assert result == "line-1\nline-2"


def test_bash_serialize_result_empty() -> None:
    tool = BashTool()
    output = {"stdout": "", "exitCode": 0, "truncated": False}
    result = tool.serialize_result(output)
    assert result == "(no output)"


def test_bash_serialize_result_no_longer_adds_truncation_hint() -> None:
    # serialize_result 已简化，截断/落盘由 loop 层 compressor 统一处理
    tool = BashTool()
    output = {
        "stdout": "line-4\nline-5\nline-6",
        "exitCode": 0,
        "truncated": True,
    }
    result = tool.serialize_result(output)
    assert result == "line-4\nline-5\nline-6"


def test_bash_serialize_result_strips_leading_newlines() -> None:
    tool = BashTool()
    output = {"stdout": "\n\nhello", "exitCode": 0, "truncated": False}
    result = tool.serialize_result(output)
    assert result == "hello"


def test_bash_serialize_result_error() -> None:
    tool = BashTool()
    result = tool.serialize_result(None, error="Command timed out")
    assert result == "Command timed out"
