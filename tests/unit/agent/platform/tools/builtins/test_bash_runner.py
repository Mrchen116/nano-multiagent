"""Tests for bash_runner module — subprocess execution layer for BashTool.

Verifies:
- BashRunner can be constructed with BashRunnerConfig
- BashRunner.run_stream executes commands and returns CommandExecution
- BashRunnerConfig has expected fields with defaults
- BashTool._run_legacy_sync calls BashRunner, NOT ctx.safety.run_command_stream
"""

import os
import signal
import time

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# These imports will fail (Red) until bash_runner.py is created.
from agent.platform.tools.builtins.bash_runner import (
    BashRunner,
    BashRunnerConfig,
)
from agent.platform.tools.safety import CommandExecution


def _pid_alive(pid: int) -> bool:
    """Return True if pid is still alive (POSIX). Reaps nothing; just probes."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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


class TestBashRunnerProcessGroup:
    """bugfix-417-M2 (决策 6, C 层): 进程组隔离 + 超时杀整组。

    现状 bug：`Popen` 无 `start_new_session`，超时只 `process.kill()` 杀直接子 bash，
    `npm run build` 的 node/vite/tsc 孙进程被孤儿化、继续持有 stdout 写端。
    """

    def test_runs_in_dedicated_process_group(self, tmp_path):
        """子 bash 在独立进程组里（pgid == 自身 pid），不属于 pytest 的进程组。"""
        runner = BashRunner(config=BashRunnerConfig())
        # 子进程打印自己的 pgid 与 pid；start_new_session=True 时二者相等
        # 且都不等于本测试进程的 pgid。
        result = runner.run_stream(
            command='echo "PGID=$(ps -o pgid= -p $$ | tr -d " ") PID=$$"',
            cwd=tmp_path,
            timeout=10.0,
            tool_name="bash",
            on_event=None,
            heartbeat_interval=0.5,
        )
        assert result.exit_code == 0
        output = Path(result.output_file_path).read_text(encoding="utf-8")
        # 解析 PGID / PID
        parts = dict(tok.split("=", 1) for tok in output.split() if "=" in tok)
        child_pgid = int(parts["PGID"])
        child_pid = int(parts["PID"])
        # 独立 session leader：子 bash 的 pgid == 自身 pid
        assert child_pgid == child_pid, (
            f"expected child to lead its own process group, got pgid={child_pgid} pid={child_pid}"
        )
        # 且不等于本测试进程的进程组（确实脱离了调用方进程组）
        assert child_pgid != os.getpgrp()

    def test_timeout_kills_descendant_process_tree(self, tmp_path):
        """超时杀整组：派生的孙进程在超时后不残留（不被孤儿化继续存活）。

        命令派生一个孙进程（pid 写文件），父 bash `wait` 直到 timeout 被掐。
        孙进程 stdout 重定向到 /dev/null（不持父写端，隔离掉 drain 维度——
        本测试只验"整组被杀"这一个不变量；drain 维度由 NonBlockingDrain 类覆盖）。
        现状只杀直接子 bash → 孙进程残留存活；修复后 killpg 整组 → 孙进程被杀。

        孙进程睡眠 30s（有限，测试本身会显式清理它兜底），确保在探测窗口内
        若未被信号杀死则仍存活，使断言可靠且测试不会无限挂死。
        """
        pidfile = tmp_path / "grandchild.pid"
        command = f"sleep 30 >/dev/null 2>&1 & echo $! > {pidfile}; wait"
        runner = BashRunner(config=BashRunnerConfig())
        start = time.monotonic()
        result = runner.run_stream(
            command=command,
            cwd=tmp_path,
            timeout=1.0,
            tool_name="bash",
            on_event=None,
            heartbeat_interval=0.2,
        )
        elapsed = time.monotonic() - start
        grandchild_pid = int(pidfile.read_text().strip())
        try:
            assert result.timed_out is True
            assert elapsed < 10.0, f"run_stream wedged for {elapsed:.1f}s after timeout"
            # 给信号传播一点时间；若整组被杀，孙进程很快消失
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and _pid_alive(grandchild_pid):
                time.sleep(0.05)
            assert not _pid_alive(grandchild_pid), (
                f"grandchild pid={grandchild_pid} survived timeout — process group not killed"
            )
        finally:
            # 兜底清理：现状（未修复）下孙进程会残留，避免污染主机
            if _pid_alive(grandchild_pid):
                try:
                    os.kill(grandchild_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


class TestBashRunnerNonBlockingDrain:
    """bugfix-417-M2 (决策 6, C 层): 收尾 drain 不被孤儿持写端挂死。

    现状 bug：超时杀直接子 bash 后，孤儿孙进程仍持 stdout 写端，
    收尾 `process.stdout.read()` 阻塞读永等不到 EOF → 承载 tool.run() 的线程挂死。
    """

    def test_drain_does_not_wedge_when_orphan_holds_write_end(self, tmp_path):
        """孙进程持 stdout 写端并存活时，超时收尾必须及时返回，不无限阻塞。

        关键复现：孙进程持有继承来的 stdout 写端且长时间存活（不退出），
        现状阻塞 drain 会永等 EOF。修复后 killpg 杀掉持写端的孙进程 +
        非阻塞/带超时 drain → 执行线程必然解封。
        """
        # 孙进程继承 stdout（未重定向），持有写端；睡眠 8s（有限，长于
        # timeout+宽限）。现状阻塞 drain 会一直等到孙进程 8s 后退出释放写端，
        # elapsed≈8s（红）；修复后 killpg 杀掉持写端孙进程 + 非阻塞 drain，
        # elapsed≈timeout（绿）。有限 sleep 保证最坏情况测试也能自终止。
        command = "sleep 8 & wait"
        runner = BashRunner(config=BashRunnerConfig())
        timeout = 1.0
        grace = 3.0
        start = time.monotonic()
        result = runner.run_stream(
            command=command,
            cwd=tmp_path,
            timeout=timeout,
            tool_name="bash",
            on_event=None,
            heartbeat_interval=0.2,
        )
        elapsed = time.monotonic() - start
        assert result.timed_out is True
        assert elapsed < timeout + grace, (
            f"drain wedged: run_stream took {elapsed:.1f}s "
            f"(> timeout {timeout}s + grace {grace}s) — orphan held write end"
        )


class TestBashToolUsesRunnerNotSafety:
    """BashTool._run_legacy_sync 不再调用 ctx.safety.run_command_stream。"""

    def test_legacy_sync_calls_bash_runner(self, tmp_path):
        """_run_legacy_sync uses BashRunner.run_stream, not ctx.safety (M6 D10).

        After M6, ToolSafety has no run_command_stream. This test verifies:
        1. ToolSafety no longer has run_command_stream
        2. BashTool.run succeeds (uses BashRunner internally)
        """
        from agent.platform.tools.builtins.bash import BashTool
        from agent.core.tools.base import (
            ToolContext,
            set_tool_safety_factory,
            set_tool_safety_config_factory,
        )
        from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig
        from agent.platform.tools.builtins.bash_runner import BashRunner

        # ToolSafety must NOT have run_command_stream after M6
        assert not hasattr(ToolSafety, "run_command_stream"), (
            "ToolSafety.run_command_stream must be deleted in M6; BashRunner owns execution"
        )

        # Set up ToolContext with platform factories
        set_tool_safety_factory(
            lambda *, repo_root, config: ToolSafety(repo_root=repo_root, config=config)
        )
        set_tool_safety_config_factory(ToolSafetyConfig)

        ctx = ToolContext.create(repo_root=tmp_path)
        tool = BashTool()

        # Verify BashRunner.run_stream is invoked by patching it
        with patch.object(BashRunner, "run_stream") as mock_run_stream:
            from agent.platform.tools.safety import CommandExecution as CE

            mock_run_stream.return_value = CE(
                exit_code=0, text="test_m6\n", truncated=False
            )
            result = tool.run({"command": "echo test_m6"}, ctx)
            mock_run_stream.assert_called_once()
