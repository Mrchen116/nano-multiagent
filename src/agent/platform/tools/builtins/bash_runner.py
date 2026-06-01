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

import os
import selectors
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

        process = subprocess.Popen(  # noqa: S603
            ["bash", "-c", command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
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
                        process.kill()

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
                    process.kill()
            finally:
                selector.close()

            # Drain remaining stdout
            remaining = process.stdout.read()
            if remaining:
                chunk = remaining.decode("utf-8", errors="replace")
                if bytes_written < MAX_FILE_BYTES:
                    out_f.write(chunk)
                    out_f.flush()
                    bytes_written += len(chunk.encode("utf-8"))
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
