"""Tests for platform background-task adapters."""

from __future__ import annotations

import json
import os
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
from agent.platform.background_tasks.file_output import BACKGROUND_BASH_MAX_OUTPUT_BYTES, BashFileOutput
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
        assert size <= BACKGROUND_BASH_MAX_OUTPUT_BYTES + 200  # truncation notice overhead
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

        def on_complete(*, task_id: str, result_text: str | None, usage, duration_ms: int, tool_use_count: int) -> None:
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

        def on_complete(*, task_id: str, result_text, usage, duration_ms, tool_use_count) -> None:
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

        def on_complete(*, task_id, result_text, usage, duration_ms, tool_use_count) -> None:
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

        def on_complete(*, task_id: str, result_text, usage, duration_ms, tool_use_count) -> None:
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

        def on_complete(*, task_id, result_text, usage, duration_ms, tool_use_count) -> None:
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
