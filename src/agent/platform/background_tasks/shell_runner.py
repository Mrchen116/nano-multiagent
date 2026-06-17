"""Background bash runner using subprocess.Popen.

bugfix-417-M4 (决策 8): ShellRunner 是**前台 + 后台唯一的 bash 执行引擎**。
``build_kernel`` 无条件 ``wire_background_tasks``，故 BashTool 永远持 wiring，
生产前台（``_run_foreground``）与后台（``_run_background``）bash 都经
``wiring.bash_runner.start`` 落到这里。曾经的第二套引擎
``platform/tools/builtins/bash_runner.py``（``BashRunner.run_stream``）是生产死路、
只被单测命中，已随本 milestone 删除——所有 bash 进程组隔离 / killpg 整树回收 /
非阻塞 drain 等能力统一收敛到本类，杜绝"修在死路、live 全挂"重演。

进程组治理（决策 6/9，最小侵入 pump→文件模型，不改回显/截断语义）：
- ``Popen(start_new_session=True)`` 让子 bash 成为新进程组 leader（pgid==pid），
  npm/build 派生的孙进程同属该组。
- 超时 / stop 用 ``os.killpg`` 对 ``-pgid`` 发 SIGTERM 宽限后 SIGKILL 杀**整组**，
  而非只 ``process.kill()`` 直接子 bash 留下持 stdout 写端的孤儿孙进程。
- killpg 后关闭 Popen 的 stdout/stderr fd，让阻塞在 ``read`` 上的 pump 线程立即
  见 EOF 解封；join 带超时兜底，孤儿持写端的极端情况下执行线程也必然解封
  （bugfix-417 C 层事故链最后一环）。
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from agent.core.background_tasks.interfaces import (
    BackgroundBashRunner,
    BackgroundTaskOutput,
    BackgroundTaskStopper,
    TaskCompletionCallback,
    TaskFailureCallback,
)

logger = logging.getLogger(__name__)

# 进程退出后 pipe write 端关闭,pump 的 read() 几乎瞬间 EOF 退出。10s 是
# 防御性硬保底,正常路径微秒级即可返回。超时不抛错(避免上层永久阻塞),只
# 记 warning 让排障可见;此时输出文件可能截断,语义退化到修复前。
_PUMP_JOIN_TIMEOUT_S = 10.0

# 进程组终止宽限期：先 SIGTERM 给整组一个机会自行退出（flush 输出/善后），
# 宽限内仍未退则升级 SIGKILL 强杀。远小于任何工具 timeout，不影响超时及时性。
_PROCESS_GROUP_TERM_GRACE_S = 2.0


class ShellRunner(BackgroundBashRunner):
    """Run shell commands with stdout/stderr capture — the sole bash engine.

    Used by both the foreground path (``BashTool._run_foreground``, which provides
    run-liveness heartbeats during the wait) and the background path
    (``BashTool._run_background``). See module docstring for why this is the only
    engine.
    """

    def __init__(self, *, safety: Any | None = None) -> None:
        self._safety = safety
        self._processes: dict[str, subprocess.Popen] = {}
        # Task ids whose exit was caused by an explicit stop() (killpg), so the monitor
        # can tell a stop-induced signal exit apart from a genuine non-zero failure and
        # not emit on_fail for it — letting TaskStopTool's registry.kill own the KILLED
        # terminal (bugfix-417-M4 fix-r1: prior to this the monitor's on_fail(exit -15)
        # raced ahead and the bubble showed「失败」instead of「已终止」).
        self._stopped: set[str] = set()
        self._lock = threading.Lock()

    def start(
        self,
        *,
        command: str,
        cwd: Path,
        output: BackgroundTaskOutput,
        task_id: str,
        timeout: float | None,
        on_complete: TaskCompletionCallback,
        on_fail: TaskFailureCallback,
    ) -> BackgroundTaskStopper:
        # M6 D10: Policy single-point — already checked in BashTool.check_permissions
        # via the auto_mode_gate hook. shell_runner trusts that decision.
        # Any caller bypassing ToolRegistry must call bash_policy.check_command_policy
        # directly (see bash_policy.py module docstring for the contract).

        # start_new_session=True：子 bash 成为新进程组/会话 leader（pgid==pid），
        # 派生的孙进程同属该组，超时/stop 时按 -pgid 杀整树（bugfix-417-M4 决策 6）。
        process = subprocess.Popen(
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            start_new_session=True,
        )
        with self._lock:
            self._processes[task_id] = process

        pump_stdout = self._start_pump(process.stdout, task_id, output, "stdout")
        pump_stderr = self._start_pump(process.stderr, task_id, output, "stderr")

        def _drain_pumps() -> None:
            # 进程退出 ≠ 输出就绪:pipe 缓冲区里的字节由 pump 线程异步落盘。
            # callback 触发前必须 join,否则 foreground 调用方会在 pump 写完前
            # 读到空文件(bugfix-354)。
            for thread, label in ((pump_stdout, "stdout"), (pump_stderr, "stderr")):
                thread.join(timeout=_PUMP_JOIN_TIMEOUT_S)
                if thread.is_alive():
                    logger.warning(
                        "shell_runner pump join timed out task_id=%s stream=%s; "
                        "output may be truncated",
                        task_id,
                        label,
                    )

        def _force_unblock_pumps() -> None:
            # killpg 后整组应已死，pump 的 read 见 EOF 自然返回；但孤儿孙进程持
            # 写端的极端情况下 read 仍会阻塞。关闭 Popen 持有的读端 fd 让阻塞的
            # read 立即抛错/返回，保证 pump 线程解封、_drain_pumps 不挂死
            # （bugfix-417 C 层：阻塞 drain 永等 EOF 锁死执行线程）。
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass

        def _monitor() -> None:
            start = time.monotonic()
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_process_group(process)
                _force_unblock_pumps()
                _drain_pumps()
                with self._lock:
                    self._processes.pop(task_id, None)
                on_fail(task_id=task_id, error=f"timed out after {timeout}s")
                return
            except Exception as exc:
                _force_unblock_pumps()
                _drain_pumps()
                with self._lock:
                    self._processes.pop(task_id, None)
                on_fail(task_id=task_id, error=str(exc))
                return

            _drain_pumps()
            duration_ms = int((time.monotonic() - start) * 1000)
            with self._lock:
                self._processes.pop(task_id, None)
                was_stopped = task_id in self._stopped
                self._stopped.discard(task_id)
            if was_stopped:
                # Exit caused by stop() → killpg, not a real failure. Stay silent so
                # TaskStopTool's registry.kill claims the KILLED terminal (bubble shows
                # 「已终止」). Emitting on_fail here would flip it to FAILED first.
                return
            if exit_code == 0:
                on_complete(
                    task_id=task_id,
                    result_text=None,
                    usage=None,
                    duration_ms=duration_ms,
                    tool_use_count=0,
                )
            else:
                on_fail(task_id=task_id, error=f"exit code {exit_code}")

        threading.Thread(target=_monitor, daemon=True).start()

        return _ProcessStopper(self, task_id)

    def _start_pump(
        self,
        stream: Any,
        task_id: str,
        output: BackgroundTaskOutput,
        label: str,
    ) -> threading.Thread:
        def _pump() -> None:
            buffer = ""
            try:
                while True:
                    chunk_bytes = stream.read(4096)
                    if not chunk_bytes:
                        if buffer:
                            output.append(task_id, buffer, stream=label)  # type: ignore[arg-type]
                        break
                    buffer += chunk_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        output.append(task_id, line + "\n", stream=label)  # type: ignore[arg-type]
            except Exception:
                pass

        thread = threading.Thread(target=_pump, daemon=True)
        thread.start()
        return thread

    def _stop_task(self, task_id: str) -> None:
        with self._lock:
            process = self._processes.pop(task_id, None)
            if process is not None:
                # Mark BEFORE killpg so the monitor (which may observe the killed
                # process within microseconds) sees the flag and suppresses on_fail.
                self._stopped.add(task_id)
        if process is None:
            return

        # stop 与超时同样杀整组（killpg），而非 process.terminate() 只触及子 bash
        # 留下孤儿孙进程（bugfix-417-M4 决策 6）。但 SIGTERM→SIGKILL 宽限轮询会阻塞
        # 调用方最长 _PROCESS_GROUP_TERM_GRACE_S；stop 的调用方（TaskStopTool）紧接着
        # 要在 registry 抢先写 KILLED 终态。若在此同步等宽限，monitor 线程的
        # process.wait() 会在宽限期内先返回 → on_fail 抢先写 FAILED，stop 语义被改
        # 成"失败"。故 stop 路径把整组回收放后台线程异步做，调用方立即返回，让
        # registry.kill 先落 KILLED；timeout 路径（_monitor 内）仍同步等宽限不变。
        threading.Thread(
            target=_kill_process_group, args=(process,), daemon=True
        ).start()


def _kill_process_group(process: subprocess.Popen) -> None:
    """SIGTERM 整个进程组、宽限后 SIGKILL，回收 bash 派生的整棵进程树。

    依赖 Popen(start_new_session=True)：子 bash 是进程组 leader，pgid==pid，
    其派生的孙进程同属该组。``os.killpg`` 对 ``-pgid`` 发信号杀整组，而非只杀
    直接子进程留下持 stdout 写端的孤儿（bugfix-417 C 层根因）。

    幂等且容错：进程已退出 / 进程组已不存在时 ``os.getpgid`` 抛 ProcessLookupError，
    静默跳过——回收是尽力而为，不应让 race 抛出影响上层收尾。
    """
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return

    def _signal_group(sig: int) -> bool:
        try:
            os.killpg(pgid, sig)
            return True
        except ProcessLookupError:
            return False

    if not _signal_group(signal.SIGTERM):
        return

    # OS-level wait for the grace window instead of a 0.05s busy-poll. Only the group
    # leader (the child bash) is reaped by wait(); a still-alive group then gets SIGKILL.
    try:
        process.wait(timeout=_PROCESS_GROUP_TERM_GRACE_S)
    except subprocess.TimeoutExpired:
        pass

    if process.poll() is None:
        _signal_group(signal.SIGKILL)


class _ProcessStopper:
    def __init__(self, runner: ShellRunner, task_id: str) -> None:
        self._runner = runner
        self._task_id = task_id

    def stop(self) -> None:
        self._runner._stop_task(self._task_id)
