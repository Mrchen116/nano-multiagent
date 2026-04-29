"""Background bash runner using subprocess.Popen."""

from __future__ import annotations

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


class ShellRunner(BackgroundBashRunner):
    """Run shell commands in the background with stdout/stderr capture."""

    def __init__(self, *, safety: Any | None = None) -> None:
        self._safety = safety
        self._processes: dict[str, subprocess.Popen] = {}
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
        if self._safety is not None:
            enforce = getattr(self._safety, "enforce_command_policy", None)
            if callable(enforce):
                enforce(command, tool_name="bash", allow_unlisted=False)

        process = subprocess.Popen(
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        with self._lock:
            self._processes[task_id] = process

        self._start_pump(process.stdout, task_id, output, "stdout")
        self._start_pump(process.stderr, task_id, output, "stderr")

        def _monitor() -> None:
            start = time.monotonic()
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    exit_code = process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    exit_code = -9
                on_fail(task_id=task_id, error=f"timed out after {timeout}s")
                with self._lock:
                    self._processes.pop(task_id, None)
                return
            except Exception as exc:
                on_fail(task_id=task_id, error=str(exc))
                with self._lock:
                    self._processes.pop(task_id, None)
                return

            duration_ms = int((time.monotonic() - start) * 1000)
            with self._lock:
                self._processes.pop(task_id, None)
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
    ) -> None:
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

        threading.Thread(target=_pump, daemon=True).start()

    def _stop_task(self, task_id: str) -> None:
        with self._lock:
            process = self._processes.pop(task_id, None)
        if process is None:
            return
        try:
            process.terminate()
        except Exception:
            pass


class _ProcessStopper:
    def __init__(self, runner: ShellRunner, task_id: str) -> None:
        self._runner = runner
        self._task_id = task_id

    def stop(self) -> None:
        self._runner._stop_task(self._task_id)
