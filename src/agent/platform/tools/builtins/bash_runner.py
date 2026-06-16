"""Bash subprocess execution layer — extracted from ToolSafety.run_command_stream.

This module owns the subprocess mechanics for foreground bash command execution.
It is decoupled from policy (bash_policy.py) and from ToolSafety's config schema.
BashTool's _run_legacy_sync path uses this instead of ctx.safety.run_command_stream.

Design notes:
- BashRunner does NOT check command policy; that is done in BashTool.check_permissions
  (D10 single-point principle).
- allow_unlisted parameter is retained on run_stream for API compatibility with
  callers that pre-date M6, but has no effect on policy (policy is already checked
  before run_stream is called).
"""

from __future__ import annotations

import errno
import os
import selectors
import signal
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
import subprocess

from agent.core.errors import ToolError
from agent.platform.tools.constants import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES
from agent.platform.tools.safety import CommandExecution


@dataclass(frozen=True, slots=True)
class BashRunnerConfig:
    """Configuration for BashRunner subprocess execution mechanics.

    Decoupled from ToolSafetyConfig — this covers only the runtime execution
    budget for a single bash command invocation.
    """

    bash_max_output_lines: int = DEFAULT_MAX_LINES
    bash_max_output_bytes: int = DEFAULT_MAX_BYTES
    bash_default_timeout: float = 30.0


class BashRunner:
    """Subprocess executor for foreground bash commands.

    Extracted from ToolSafety.run_command_stream; behaviour is identical.
    Callers must NOT call run_stream with commands that haven't passed
    BashTool.check_permissions — policy is not rechecked here (D10).
    """

    def __init__(self, config: BashRunnerConfig) -> None:
        self._config = config

    def run_stream(
        self,
        *,
        command: str,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
        allow_unlisted: bool = False,  # retained for API compat, unused post-M6
        on_event: Callable[[Mapping[str, Any]], None] | None = None,
        heartbeat_interval: float = 0.5,
    ) -> CommandExecution:
        """Run command and optionally emit realtime execution progress events.

        Identical subprocess mechanics to the original ToolSafety.run_command_stream.
        Policy is NOT rechecked here — trust the hook's check_permissions decision.
        """
        repo_tmp = cwd / ".agent" / "tmp"
        repo_tmp.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix="bash-stdout-", suffix=".log", dir=repo_tmp
        )
        os.close(tmp_fd)

        MAX_FILE_BYTES = 1 * 1024 * 1024  # 1MB hard cap

        # start_new_session=True 让子 bash 成为新进程组/会话 leader（pgid==pid），
        # 这样 npm/build 派生的孙进程都落在同一进程组里。超时/中断时按进程组
        # （-pgid）发信号即可整棵进程树一起回收，而非只杀直接子 bash 留下孤儿
        # 孙进程持 stdout 写端、致收尾 drain 永等不到 EOF（bugfix-417 C 层根因）。
        process = subprocess.Popen(  # noqa: S603
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            start_new_session=True,
        )
        if process.stdout is None:
            raise ToolError("command stream unavailable", tool_name=tool_name)

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, data="stdout")

        start_monotonic = time.monotonic()
        deadline = start_monotonic + timeout if timeout is not None else None
        last_heartbeat = start_monotonic
        seq = 0
        timed_out = False
        aborted = False
        bytes_written = 0
        was_limited = False

        _emit_event(
            on_event,
            {"phase": "started", "status": "started", "elapsed_ms": 0},
        )

        with open(tmp_path, "w", encoding="utf-8") as out_f:
            try:
                while True:
                    now = time.monotonic()
                    if (
                        deadline is not None
                        and now >= deadline
                        and process.poll() is None
                    ):
                        timed_out = True
                        _kill_process_group(process)

                    wait_timeout = heartbeat_interval
                    if deadline is not None:
                        wait_timeout = min(wait_timeout, max(0.0, deadline - now))

                    for key, _ in selector.select(timeout=wait_timeout):
                        chunk_bytes = os.read(key.fileobj.fileno(), 4096)
                        if not chunk_bytes:
                            selector.unregister(key.fileobj)
                            continue
                        chunk = chunk_bytes.decode("utf-8", errors="replace")

                        if bytes_written < MAX_FILE_BYTES:
                            out_f.write(chunk)
                            out_f.flush()
                            bytes_written += len(chunk.encode("utf-8"))
                        else:
                            was_limited = True

                        seq += 1
                        _emit_event(
                            on_event, {"phase": "chunk", "chunk": chunk, "seq": seq}
                        )

                    current = time.monotonic()
                    if process.poll() is not None and not selector.get_map():
                        break
                    if (
                        process.poll() is None
                        and current - last_heartbeat >= heartbeat_interval
                    ):
                        last_heartbeat = current
                        _emit_event(
                            on_event,
                            {
                                "phase": "running",
                                "status": "running",
                                "elapsed_ms": int((current - start_monotonic) * 1000),
                            },
                        )
            except KeyboardInterrupt:
                aborted = True
                if process.poll() is None:
                    _kill_process_group(process)
            finally:
                selector.close()

            # Drain remaining stdout. 用非阻塞带超时读取，而非阻塞 process.stdout.read()：
            # 后者会等所有持写端的进程关闭 fd 才返回 EOF；若有孤儿孙进程持写端不退，
            # 阻塞读会永挂死承载本调用的执行线程（bugfix-417 C 层事故链的最后一环）。
            # 正常路径（进程已退、写端已关）下非阻塞读同样能读完残余字节并见 EOF。
            chunk = _drain_nonblocking(process.stdout)
            if chunk:
                text_chunk = chunk.decode("utf-8", errors="replace")
                if bytes_written < MAX_FILE_BYTES:
                    out_f.write(text_chunk)
                    out_f.flush()
                    bytes_written += len(text_chunk.encode("utf-8"))
                else:
                    was_limited = True

            process.wait()

        exit_code = int(process.returncode if process.returncode is not None else 0)
        duration_ms = int((time.monotonic() - start_monotonic) * 1000)
        if aborted:
            status_text = "aborted"
        elif timed_out:
            status_text = "timeout"
        elif exit_code == 0:
            status_text = "completed"
        else:
            status_text = "failed"

        _emit_event(
            on_event,
            {
                "phase": "exit",
                "status": status_text,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            },
        )

        file_size = os.path.getsize(tmp_path)
        return CommandExecution(
            exit_code=exit_code,
            text="",
            truncated=was_limited,
            output_file_path=tmp_path,
            file_size=file_size,
            timed_out=timed_out,
            aborted=aborted,
            timeout=timeout,
        )


def _emit_event(
    callback: Callable[[Mapping[str, Any]], None] | None,
    payload: Mapping[str, Any],
) -> None:
    """Fire event to callback without letting exceptions propagate."""
    if callback is None:
        return
    try:
        callback(dict(payload))
    except Exception:
        return


# 进程组终止宽限期：先 SIGTERM 给整组一个机会自行退出（flush 输出/善后），
# 这一段时间内仍未退则升级 SIGKILL 强杀。取值远小于任何工具 timeout，
# 不影响超时及时性，又给子进程留出干净收尾的窗口（决策 6）。
_PROCESS_GROUP_TERM_GRACE = 2.0
# drain 总时限：进程组已被 killpg 后写端应很快关闭；给一个上限兜底，
# 即使个别孤儿仍持写端，执行线程也必然在此时限内解封，不挂死。
_DRAIN_TIMEOUT = 2.0


def _kill_process_group(process: subprocess.Popen) -> None:
    """SIGTERM 整个进程组、宽限后 SIGKILL，回收 bash 派生的整棵进程树。

    依赖 Popen(start_new_session=True)：子 bash 是进程组 leader，pgid==pid，
    其派生的孙进程同属该组。`os.killpg` 对 -pgid 发信号杀整组，而非只杀直接
    子进程留下持 stdout 写端的孤儿（bugfix-417 C 层根因）。

    幂等且容错：进程已退出 / 进程组已不存在时 `os.getpgid` 抛 ProcessLookupError，
    静默跳过——回收是尽力而为，不应让 race 抛出影响上层收尾。
    """
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return

    def _signal_group(sig: int) -> bool:
        """对进程组发信号；组已不存在返回 False。"""
        try:
            os.killpg(pgid, sig)
            return True
        except ProcessLookupError:
            return False

    if not _signal_group(signal.SIGTERM):
        return

    # 宽限期内轮询进程组是否已整体退出（leader 退出后用 kill(pgid, 0) 探测组存活）
    deadline = time.monotonic() + _PROCESS_GROUP_TERM_GRACE
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(0.05)

    # 仍存活则强杀整组
    if process.poll() is None:
        _signal_group(signal.SIGKILL)


def _drain_nonblocking(stream) -> bytes:
    """非阻塞带超时地读尽 stream 残余字节，永不无限阻塞。

    将底层 fd 切到非阻塞模式后循环读：读到 EOF（b"")即收尾完成；EAGAIN/EWOULDBLOCK
    表示暂无数据，用 selector 等一小段，超过 `_DRAIN_TIMEOUT` 总时限则放弃（孤儿
    持写端的极端情况），保证承载执行线程必然解封（bugfix-417 C 层）。
    """
    fd = stream.fileno()
    os.set_blocking(fd, False)
    selector = selectors.DefaultSelector()
    selector.register(fd, selectors.EVENT_READ)
    collected = bytearray()
    deadline = time.monotonic() + _DRAIN_TIMEOUT
    try:
        while time.monotonic() < deadline:
            try:
                chunk = os.read(fd, 4096)
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # 暂无数据：等下一次可读或超时
                    selector.select(timeout=max(0.0, deadline - time.monotonic()))
                    continue
                raise
            if not chunk:  # EOF — 写端全部关闭
                break
            collected.extend(chunk)
    finally:
        selector.close()
    return bytes(collected)
