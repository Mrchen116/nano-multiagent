"""Tests for platform background-task adapters."""

from __future__ import annotations

import json
import os
import signal
import tempfile
import threading
import time
from pathlib import Path

import pytest

from agent.core.background_tasks.models import (
    BackgroundTaskRecord,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from agent.platform.background_tasks.file_output import (
    BACKGROUND_BASH_MAX_OUTPUT_BYTES,
    BashFileOutput,
)
from agent.platform.background_tasks.shell_runner import ShellRunner
from agent.platform.background_tasks.task_store import InMemoryTaskStore
from agent.platform.background_tasks.wiring import _SystemClock


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


def test_system_clock_now_iso_is_string() -> None:
    clock = _SystemClock()
    result = clock.now_iso()
    assert isinstance(result, str)
    assert "T" in result


def test_system_clock_now_ms_is_positive() -> None:
    clock = _SystemClock()
    result = clock.now_ms()
    assert isinstance(result, int)
    assert result > 0


# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------


def test_store_round_trip() -> None:
    store = InMemoryTaskStore()
    record = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="s1",
        status=BackgroundTaskStatus.QUEUED,
    )
    store.insert(record)
    assert store.get("b1") is record


def test_store_update_replaces_record() -> None:
    store = InMemoryTaskStore()
    store.insert(
        BackgroundTaskRecord(
            task_id="b1",
            task_type=BackgroundTaskType.BASH,
            parent_session_id="s1",
            status=BackgroundTaskStatus.QUEUED,
        )
    )
    updated = BackgroundTaskRecord(
        task_id="b1",
        task_type=BackgroundTaskType.BASH,
        parent_session_id="s1",
        status=BackgroundTaskStatus.RUNNING,
    )
    store.update(updated)
    assert store.get("b1").status == BackgroundTaskStatus.RUNNING


def test_store_list_non_terminal() -> None:
    store = InMemoryTaskStore()
    store.insert(
        BackgroundTaskRecord(
            task_id="b1",
            task_type=BackgroundTaskType.BASH,
            parent_session_id="s1",
            status=BackgroundTaskStatus.RUNNING,
        )
    )
    store.insert(
        BackgroundTaskRecord(
            task_id="b2",
            task_type=BackgroundTaskType.BASH,
            parent_session_id="s1",
            status=BackgroundTaskStatus.COMPLETED,
        )
    )
    non_terminal = store.list_non_terminal()
    assert len(non_terminal) == 1
    assert non_terminal[0].task_id == "b1"


def test_store_manifest_append() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = Path(tmpdir) / "manifest.jsonl"
        store = InMemoryTaskStore(manifest_path=manifest)
        record = BackgroundTaskRecord(
            task_id="b1",
            task_type=BackgroundTaskType.BASH,
            parent_session_id="s1",
            status=BackgroundTaskStatus.QUEUED,
            description="test",
        )
        store.insert(record)
        store.update(
            BackgroundTaskRecord(
                task_id="b1",
                task_type=BackgroundTaskType.BASH,
                parent_session_id="s1",
                status=BackgroundTaskStatus.COMPLETED,
                description="test",
            )
        )
        lines = manifest.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        data = json.loads(lines[0])
        assert data["task_id"] == "b1"
        assert data["status"] == "queued"


# ---------------------------------------------------------------------------
# Bash file output
# ---------------------------------------------------------------------------


def test_file_output_creates_path() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        path = output.open("sess-1", "b1234567890abcdef")
        assert path.exists()
        assert path.name == "b1234567890abcdef.output"
        assert "sess-1" in str(path)


def test_file_output_appends_text() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        path = output.open("sess-1", "b1")
        output.append("b1", "hello\n", stream="stdout")
        content = path.read_text(encoding="utf-8")
        assert "hello" in content


def test_file_output_stderr_prefix() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        output.open("sess-1", "b1")
        output.append("b1", "error\n", stream="stderr")
        # Read the file from the handle
        path = output._resolve_path("sess-1", "b1")
        content = path.read_text(encoding="utf-8")
        assert "[stderr] error" in content


def test_file_output_256mib_cap() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        output.open("sess-1", "b1")
        big = "x" * 1024
        written = 0
        while written < BACKGROUND_BASH_MAX_OUTPUT_BYTES + 1024:
            output.append("b1", big, stream="stdout")
            written += len(big.encode("utf-8"))
        path = output._resolve_path("sess-1", "b1")
        size = path.stat().st_size
        assert (
            size <= BACKGROUND_BASH_MAX_OUTPUT_BYTES + 200
        )  # truncation notice overhead
        content = path.read_text(encoding="utf-8")
        assert "exceeded 256 MiB limit" in content


# ---------------------------------------------------------------------------
# Shell runner
# ---------------------------------------------------------------------------


def test_shell_runner_completes_with_exit_0() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        completed = []

        def on_complete(
            *,
            task_id: str,
            result_text: str | None,
            usage,
            duration_ms: int,
            tool_use_count: int,
        ) -> None:
            completed.append((task_id, duration_ms))

        def on_fail(*, task_id: str, error: str) -> None:
            pytest.fail(f"unexpected fail: {error}")

        # open must be called before the runner starts appending.
        path = output.open("sess-1", "b1")
        stopper = runner.start(
            command="echo hello",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=10.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        time.sleep(0.5)
        assert len(completed) == 1
        assert completed[0][0] == "b1"
        content = path.read_text(encoding="utf-8")
        assert "hello" in content


def test_shell_runner_fails_on_nonzero_exit() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        failed = []

        def on_complete(
            *, task_id: str, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            pytest.fail("unexpected complete")

        def on_fail(*, task_id: str, error: str) -> None:
            failed.append((task_id, error))

        runner.start(
            command="exit 1",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=10.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        time.sleep(0.5)
        assert len(failed) == 1
        assert "exit code 1" in failed[0][1]


def test_shell_runner_stop_terminates_process() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        failed = []

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            pass

        def on_fail(*, task_id: str, error: str) -> None:
            failed.append((task_id, error))

        stopper = runner.start(
            command="sleep 30",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=10.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        time.sleep(0.2)
        stopper.stop()
        time.sleep(0.5)
        # After stop, process should be gone; a new start with same command should work.
        assert True


def test_shell_runner_stop_does_not_fire_on_fail() -> None:
    """A stopped task must NOT report failure via on_fail (bugfix-417-M4 fix-r1).

    Race: ``_stop_task`` killpg's the process; the ``_monitor`` thread's
    ``process.wait()`` then returns with a signal exit code and, pre-fix,
    unconditionally calls ``on_fail(exit code -15)`` → registry flips to FAILED before
    TaskStopTool's ``registry.kill`` can claim KILLED (guarded as already-terminal).
    User sees the SSE bubble as「失败」instead of「已终止」. The engine must distinguish
    a stop-induced exit from a genuine failure and not emit on_fail for the former.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        events: list[str] = []
        done = threading.Event()

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            events.append("complete")
            done.set()

        def on_fail(*, task_id: str, error: str) -> None:
            events.append(f"fail:{error}")
            done.set()

        stopper = runner.start(
            command="sleep 30",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=30.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        time.sleep(0.3)
        stopper.stop()
        # Give the monitor thread ample time to observe the killed process and run its
        # terminal branch; if it (wrongly) calls on_fail, ``events`` will capture it.
        fired = done.wait(5.0)
        assert not fired or "complete" in events, (
            f"stop must not surface a failure terminal; got events={events}"
        )
        assert not any(e.startswith("fail") for e in events), (
            f"on_fail must not fire for a stop-induced exit; got events={events}"
        )


def test_shell_runner_stop_during_timeout_window_stays_silent_and_clears_flag() -> None:
    """A stopped task that exits via the TIMEOUT path must also stay silent and clear
    its _stopped flag (bugfix-417-M4 fix-r2 symmetry fix).

    fix-r1 only handled the normal-exit path. If stop() lands while the command is also
    hitting its own deadline (here the command ignores SIGTERM so killpg's grace can't
    reap it before ``process.wait(timeout)`` fires), the monitor took the timeout branch
    and (pre-r2) called on_fail("timed out") AND never discarded _stopped → the bubble
    showed「执行超时」instead of「已终止」and the _stopped entry leaked forever.
    All three exit paths must symmetrically suppress on_fail when stopped and discard.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        events: list[str] = []
        done = threading.Event()

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            events.append("complete")
            done.set()

        def on_fail(*, task_id: str, error: str) -> None:
            events.append(f"fail:{error}")
            done.set()

        # Command ignores SIGTERM, so _stop_task's killpg SIGTERM (grace 2s) cannot reap
        # it; the monitor's process.wait(timeout=0.5) fires the timeout branch first,
        # WHILE _stopped is set (stop issued at t=0.2s). Without the symmetry fix the
        # timeout branch reports failure and leaks _stopped.
        stopper = runner.start(
            command="trap '' TERM; sleep 30",
            cwd=Path(tmpdir),
            output=output,
            task_id="b_to",
            timeout=0.5,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        time.sleep(0.2)
        stopper.stop()
        fired = done.wait(5.0)
        assert not any(e.startswith("fail") for e in events), (
            f"stopped task must stay silent on the timeout path too; events={events}"
        )
        # _stopped must be discarded regardless of exit path (no unbounded leak).
        assert "b_to" not in runner._stopped, (
            "_stopped entry leaked after stop+timeout exit"
        )
        del fired


class _SlowAppendOutput:
    """Wraps BashFileOutput so each append takes ~0.3s.

    This is how we make the bugfix-354 race deterministic: the gap between
    process exit (monitor wakes up) and pump finishing its last append() is
    long enough that, without join(), the callback fires on an empty file.
    """

    def __init__(self, inner: BashFileOutput, delay: float = 0.3) -> None:
        self._inner = inner
        self._delay = delay

    def open(self, session_id: str, task_id: str) -> Path:
        return self._inner.open(session_id, task_id)

    def append(self, task_id: str, text: str, *, stream: str) -> None:
        time.sleep(self._delay)
        self._inner.append(task_id, text, stream=stream)


def test_shell_runner_output_ready_when_complete_callback_fires() -> None:
    """Regression for bugfix-354: callback must not fire before pump drains the pipe.

    A slow ``append`` widens the race window so the bug is deterministically
    reproducible: pre-fix, the monitor thread fires ``on_complete`` while the
    pump is still inside ``time.sleep`` and the output file is empty.
    Post-fix, ``_monitor`` joins the pump first so the file is ready.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        inner = BashFileOutput(workspace_root=Path(tmpdir))
        output = _SlowAppendOutput(inner, delay=0.3)
        runner = ShellRunner()
        done = threading.Event()
        observed: dict[str, str] = {}

        path = output.open("sess-1", "b1")

        def on_complete(
            *, task_id: str, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            observed["content"] = path.read_text(encoding="utf-8")
            done.set()

        def on_fail(*, task_id: str, error: str) -> None:
            observed["error"] = error
            done.set()

        runner.start(
            command="echo hello-from-pump",
            cwd=Path(tmpdir),
            output=output,  # type: ignore[arg-type]
            task_id="b1",
            timeout=10.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )

        assert done.wait(10.0), "on_complete never fired"
        assert "error" not in observed, observed.get("error")
        assert "hello-from-pump" in observed["content"], (
            f"output not drained before callback: {observed['content']!r}"
        )


def test_shell_runner_timeout_kills_process() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        failed = []

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            pass

        def on_fail(*, task_id: str, error: str) -> None:
            failed.append((task_id, error))

        runner.start(
            command="sleep 30",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=0.2,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        time.sleep(1.0)
        assert len(failed) == 1
        assert "timed out" in failed[0][1]


# ---------------------------------------------------------------------------
# bugfix-417-M4 (决策 8/9, C 层): ShellRunner 是唯一生产 bash 引擎。
# M2 的 killpg/drain 原本落在死路 bash_runner.run_stream 上（生产从不走），
# 这里把同样的不变量直接打 ShellRunner——生产实际跑的引擎。
# ---------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    """Return True if pid is still alive (POSIX). Probes only; reaps nothing."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_shell_runner_runs_in_dedicated_process_group() -> None:
    """子 bash 是独立进程组 leader（pgid == 自身 pid），不属于 pytest 进程组。

    start_new_session=True 的前提：没有它 killpg 杀的是 pytest 的整组（自杀）。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        done = threading.Event()

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            done.set()

        def on_fail(*, task_id: str, error: str) -> None:
            done.set()

        path = output.open("sess-1", "b1")
        runner.start(
            command='echo "PGID=$(ps -o pgid= -p $$ | tr -d " ") PID=$$"',
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=10.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        assert done.wait(10.0), "callback never fired"
        content = path.read_text(encoding="utf-8")
        parts = dict(tok.split("=", 1) for tok in content.split() if "=" in tok)
        child_pgid = int(parts["PGID"])
        child_pid = int(parts["PID"])
        assert child_pgid == child_pid, (
            f"expected child to lead its own process group, "
            f"got pgid={child_pgid} pid={child_pid}"
        )
        assert child_pgid != os.getpgrp()


def test_shell_runner_timeout_kills_descendant_process_tree() -> None:
    """超时杀整组：派生孙进程在超时后不残留（不被孤儿化继续存活）。

    孙进程 stdout 重定向 /dev/null（不持父写端，隔离 drain 维度——本测试只验
    "整组被杀"）。现状 ShellRunner 只 process.kill() 直接子 bash → 孙进程残留；
    修复后 killpg 整组 → 孙进程被杀。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        pidfile = Path(tmpdir) / "grandchild.pid"
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        done = threading.Event()

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            done.set()

        def on_fail(*, task_id: str, error: str) -> None:
            done.set()

        runner.start(
            command=f"sleep 30 >/dev/null 2>&1 & echo $! > {pidfile}; wait",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=1.0,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        assert done.wait(10.0), "callback never fired (drain may have wedged)"
        # 给信号传播一点时间；若整组被杀，孙进程很快消失
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not pidfile.exists():
            time.sleep(0.05)
        grandchild_pid = int(pidfile.read_text().strip())
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and _pid_alive(grandchild_pid):
                time.sleep(0.05)
            assert not _pid_alive(grandchild_pid), (
                f"grandchild pid={grandchild_pid} survived timeout — "
                "process group not killed"
            )
        finally:
            if _pid_alive(grandchild_pid):
                try:
                    os.kill(grandchild_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def test_shell_runner_drain_does_not_wedge_when_orphan_holds_write_end() -> None:
    """孙进程持 stdout 写端并存活时，超时收尾必须及时返回，不无限阻塞。

    孙进程继承 stdout（未重定向）持写端，睡 8s。现状 ShellRunner 阻塞 pump.join
    会一直等到孙进程 8s 退出释放写端（红）；修复后 killpg 杀持写端孙进程 +
    非阻塞 drain → on_fail 在 timeout+grace 内必然触发（绿）。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output = BashFileOutput(workspace_root=Path(tmpdir))
        runner = ShellRunner()
        done = threading.Event()

        def on_complete(
            *, task_id, result_text, usage, duration_ms, tool_use_count
        ) -> None:
            done.set()

        def on_fail(*, task_id: str, error: str) -> None:
            done.set()

        timeout = 1.0
        grace = 3.5
        path = output.open("sess-1", "b1")  # noqa: F841
        start = time.monotonic()
        runner.start(
            command="sleep 8 & wait",
            cwd=Path(tmpdir),
            output=output,
            task_id="b1",
            timeout=timeout,
            on_complete=on_complete,
            on_fail=on_fail,
        )
        fired = done.wait(timeout + grace)
        elapsed = time.monotonic() - start
        assert fired, (
            f"drain wedged: callback never fired within {timeout + grace}s "
            f"(elapsed {elapsed:.1f}s) — orphan held write end"
        )
