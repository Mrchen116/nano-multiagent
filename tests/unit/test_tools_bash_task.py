"""Unit tests for BashTool and TaskTool: execution, permissions, output handling, serialize_result."""

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.task import TaskTool
from agent.platform.tools.safety import CommandExecution
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


# ---------------------------------------------------------------------------
# BashTool execution
# ---------------------------------------------------------------------------


def test_bash_reports_non_zero_exit(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        BashTool().run({"command": 'python -c "import sys;sys.exit(7)"'}, ctx)

    assert str(exc_info.value).endswith("Command exited with code 7")
    assert exc_info.value.details["exitCode"] == 7
    assert exc_info.value.details["tool_name"] == "bash"
    assert "content" in exc_info.value.details


def test_bash_handles_timeout(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(
        ToolError, match="Command timed out after 0.05 seconds"
    ) as exc_info:
        BashTool().run(
            {
                "command": (
                    'python -c "import time; '
                    "print('before-timeout', flush=True); "
                    'time.sleep(0.3)"'
                ),
                "timeout": 0.05,
            },
            ctx,
        )
    assert exc_info.value.details["timedOut"] is True
    assert exc_info.value.details["timeout"] == 0.05
    assert exc_info.value.details["tool_name"] == "bash"
    assert isinstance(exc_info.value.details["content"], str)


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


def test_bash_file_mode_no_truncation_for_small_output(tmp_path: Path) -> None:
    # 文件模式下，小输出（<1MB）不被 safety 层截断
    ctx = _context(tmp_path)

    result = BashTool().run(
        {"command": "python -c \"[print(f'line-{i}') for i in range(10)]\""},
        ctx,
    )

    assert result["truncated"] is False
    assert "line-0" in result["stdout"]
    assert "line-9" in result["stdout"]


def test_bash_file_mode_1mb_hard_limit(tmp_path: Path) -> None:
    # 文件模式下，超过 1MB 的输出被硬上限截断
    ctx = _context(tmp_path)

    result = BashTool().run(
        {"command": "python -c \"print('x' * (2 * 1024 * 1024))\""},
        ctx,
    )

    assert result["truncated"] is True
    assert len(result["stdout"]) <= 2 * 1024 * 1024


def test_bash_without_timeout_does_not_inject_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """After M6, BashTool uses BashRunner.run_stream, not ctx.safety.run_command_stream.
    Patch BashRunner.run_stream to verify timeout=None is passed through.
    """
    from agent.platform.tools.builtins.bash_runner import BashRunner

    captured: dict[str, object] = {}

    def fake_run_stream(  # noqa: ANN202
        self,  # noqa: ANN001
        *,
        command: str,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
        allow_unlisted: bool = False,
        on_event=None,  # noqa: ANN001,ARG001
        heartbeat_interval: float = 0.5,  # noqa: ARG001
    ) -> CommandExecution:
        del self, command, cwd, tool_name, allow_unlisted
        captured["timeout"] = timeout
        return CommandExecution(exit_code=0, text="ok", truncated=False)

    monkeypatch.setattr(BashRunner, "run_stream", fake_run_stream)
    ctx = _context(tmp_path)

    result = BashTool().run({"command": "python -c \"print('ok')\""}, ctx)

    assert captured["timeout"] is None
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


def test_bash_aborted_contract_message_and_details(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """After M6, BashTool uses BashRunner; patch BashRunner.run_stream to simulate abort."""
    from agent.platform.tools.builtins.bash_runner import BashRunner

    ctx = _context(tmp_path)

    def fake_run_stream(self, **kwargs):  # noqa: ANN001, ANN003
        del self, kwargs
        raise ToolError(
            "keyboard interrupt", tool_name="bash", details={"aborted": True}
        )

    monkeypatch.setattr(BashRunner, "run_stream", fake_run_stream)

    with pytest.raises(ToolError, match="Command aborted") as exc_info:
        BashTool().run({"command": "python -c \"print('ignored')\""}, ctx)

    assert exc_info.value.details["aborted"] is True
    assert exc_info.value.details["tool_name"] == "bash"


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


# ---------------------------------------------------------------------------
# TaskTool serialize_result
# ---------------------------------------------------------------------------


def test_task_serialize_result_completed() -> None:
    tool = TaskTool()
    output = {
        "status": "completed",
        "content": "task output",
        "sessionId": "sess_1",
        "durationMs": 123,
        "agent": "oracle",
        "continuation": False,
        "taskId": "tid_1",
    }
    result = tool.serialize_result(output)
    assert result.startswith("Task completed in 123ms.")
    assert "Agent: oracle" in result
    assert "task output" in result
    assert "session_id: sess_1" in result
    assert "task_id: tid_1" in result


def test_task_serialize_result_continuation() -> None:
    tool = TaskTool()
    output = {
        "status": "completed",
        "content": "continued output",
        "sessionId": "sess_2",
        "durationMs": 456,
        "agent": "explore",
        "continuation": True,
        "taskId": "tid_2",
    }
    result = tool.serialize_result(output)
    assert result.startswith("Task continued and completed in 456ms.")
    assert "continued output" in result
    assert "session_id: sess_2" in result


def test_task_serialize_result_empty_content() -> None:
    tool = TaskTool()
    output = {
        "status": "completed",
        "content": "",
        "sessionId": "sess_3",
        "durationMs": 10,
        "agent": "test",
        "continuation": False,
        "taskId": "tid_3",
    }
    result = tool.serialize_result(output)
    assert "(Subagent completed but returned no output.)" in result


def test_task_serialize_result_async_launched() -> None:
    tool = TaskTool()
    output = {
        "status": "async_launched",
        "taskId": "tid_4",
        "sessionId": "sess_4",
        "description": "research",
        "agent": "research (category: research)",
        "continuation": False,
    }
    result = tool.serialize_result(output)
    assert result.startswith("Background task launched.")
    assert "Task ID: tid_4" in result
    assert "Description: research" in result
    assert "Agent: research (category: research)" in result
    assert "Status: queued" in result


def test_task_serialize_result_async_continued() -> None:
    tool = TaskTool()
    output = {
        "status": "async_launched",
        "taskId": "tid_5",
        "sessionId": "sess_5",
        "description": "follow-up",
        "agent": "oracle",
        "continuation": True,
    }
    result = tool.serialize_result(output)
    assert result.startswith("Background task continued.")
    assert "Agent continues with full previous context preserved." in result


def test_task_serialize_result_failed() -> None:
    tool = TaskTool()
    output = {
        "status": "failed",
        "title": "Task failed",
        "error": "something broke",
        "sessionId": "sess_6",
    }
    result = tool.serialize_result(output)
    assert result.startswith("Task failed")
    assert "Error: something broke" in result
    assert "session_id: sess_6" in result


def test_task_serialize_result_error_passthrough() -> None:
    tool = TaskTool()
    result = tool.serialize_result(None, error="tool execution aborted")
    assert result == "tool execution aborted"


def test_task_serialize_result_non_mapping_fallback() -> None:
    tool = TaskTool()
    result = tool.serialize_result("plain string")
    assert result == "plain string"
