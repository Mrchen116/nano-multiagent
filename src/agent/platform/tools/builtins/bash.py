"""Built-in `bash` tool with policy, background execution, and output guardrails."""

import signal
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from agent.core.background_tasks.ids import generate_bash_task_id
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.tools.base import WiringMixin
from agent.platform.tools.presentation import BASH_PRESENTER as _BASH_PRESENTER
from agent.platform.tools.builtins.bash_policy import (
    check_command_policy,
)
from agent.platform.permissions.broker import PermissionDecision

# Foreground budget before auto-backgrounding (seconds)
_DEFAULT_FOREGROUND_BUDGET = 120.0

# bugfix-417-M4 R2: cadence of phase:running liveness heartbeats emitted while a
# foreground bash command runs. Must stay well below the watchdog idle timeout
# (Gateway/IM default 120s) so a silent long command (`sleep 200`) keeps producing
# run_heartbeat events and is never reaped as a stall (decision 3 calls for ≤15s).
_FOREGROUND_HEARTBEAT_INTERVAL = 10.0

_READ_ONLY_COMMANDS = frozenset(
    {
        "ls",
        "cat",
        "grep",
        "rg",
        "find",
        "head",
        "tail",
        "echo",
        "pwd",
        "wc",
        "file",
        "stat",
        "readlink",
        "sort",
        "uniq",
        "cut",
        "tr",
        "which",
        "whoami",
        "id",
        "uname",
        "date",
        "ps",
        "df",
        "du",
        "env",
        "printenv",
        "hostname",
    }
)

_READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {
        "status",
        "log",
        "diff",
        "show",
        "branch",
        "remote",
        "config",
        "rev-parse",
        "ls-files",
        "blame",
        "stash",
        "tag",
        "describe",
    }
)


class BashTool(WiringMixin):
    """Execute shell commands within `ToolSafety` command and timeout policy.

    Supports synchronous execution (default), explicit background execution
    (``run_in_background=true``), and automatic backgrounding when a
    foreground command exceeds the 15-second budget.
    """

    name = "bash"
    presenter = _BASH_PRESENTER  # 决策 12: presentation travels with the tool object
    max_result_size_chars = 30_000
    description = (
        "Execute a bash command in the current working directory. Returns stdout and stderr. "
        "Output larger than 30K chars is compressed by the result budget system. "
        "Optionally provide a timeout in seconds, or run in the background.\n\n"
        "- command: The bash command to execute.\n"
        "- description: Short description (3-5 words) for background task tracking.\n"
        "- timeout: Timeout in seconds for the command itself.\n"
        "- run_in_background: true=run in background (returns task_id immediately); "
        "false=wait for result. Default: false. Foreground commands auto-background after 15s."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Bash command to execute"},
            "description": {
                "type": "string",
                "description": "Short description for background task tracking (3-5 words).",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (optional, no default timeout)",
            },
            "run_in_background": {
                "type": "boolean",
                "description": (
                    "Set true to run this command in the background. "
                    "The call returns immediately with task_id and output_file. "
                    "You will be notified automatically when it completes."
                ),
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def __init__(self, *, wiring: Any | None = None) -> None:
        self._wiring = wiring

    def check_permissions(
        self,
        tool_input: Mapping[str, Any],
        ctx: "ToolContext",
    ) -> "PermissionDecision":
        """Classify the bash command via bash_policy and return a permission decision.

        Called by auto_mode_gate (step 1 + step 5 dispatch) before the classifier.
        Policy is applied exactly once here (D10 single-point principle).
        BashTool.run / shell_runner do NOT re-check.

        Returns:
            PermissionDecision with behavior:
              - 'allow'       if command matches BASH_ALLOWED_PREFIXES
              - 'deny'        if command matches BASH_BLOCKED_COMMANDS or BASH_BLOCKED_FRAGMENTS
              - 'passthrough' if command is unlisted (review → classifier decides)
        """
        command = str(tool_input.get("command", "")).strip()
        if not command:
            # Empty command: let schema validation handle it.
            return PermissionDecision(behavior="passthrough")

        try:
            decision = check_command_policy(command)
        except Exception:
            # Unparseable command — fail open; let tool body raise ToolError.
            return PermissionDecision(behavior="passthrough")

        if decision.status == "allowed":
            return PermissionDecision(
                behavior="allow",
                decision_reason={"type": "command_policy", "matched": "allowed"},
            )
        if decision.status == "denied":
            return PermissionDecision(
                behavior="deny",
                reason=f"bash policy denied: {decision.details.get('blocked_command', decision.details.get('blocked_fragment', ''))}",
                decision_reason={
                    "type": "command_policy",
                    "matched": "denied",
                    **dict(decision.details),
                },
            )
        # status == "review" — pass through to classifier
        return PermissionDecision(
            behavior="passthrough",
            decision_reason={
                "type": "command_policy",
                "matched": "review",
                **dict(decision.details),
            },
        )

    def is_concurrency_safe(self, args: Mapping[str, Any]) -> bool:
        """Dynamic safety: read-only commands are safe; anything with side-effects is not."""
        command = str(args.get("command", "")).strip()
        if not command:
            return False

        # Redirections, pipes, background execution, or command separators imply side-effects.
        if any(c in command for c in (">", ">>", "|", "&", ";", "`", "$(")):
            return False

        tokens = command.split()
        if not tokens:
            return False

        first = tokens[0].lower()

        # Explicit read-only commands.
        if first in _READ_ONLY_COMMANDS:
            return True

        # Git commands need fine-grained classification.
        if first == "git":
            if len(tokens) >= 2:
                sub = tokens[1].lower()
                if sub in _READ_ONLY_GIT_SUBCOMMANDS:
                    return True
            return False

        return False

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Run one shell command: background, foreground, or foreground with auto-background."""

        command = str(args["command"])
        run_in_background = bool(args.get("run_in_background", False))
        description = str(args.get("description", "")).strip()
        timeout = args.get("timeout")
        timeout_value: float | None = None
        if timeout is not None:
            timeout_value = float(timeout)
            if timeout_value <= 0:
                raise ToolError("timeout must be > 0", tool_name=self.name)

        if run_in_background:
            return self._run_background(
                command=command,
                description=description,
                timeout_value=timeout_value,
                ctx=ctx,
            )

        # Foreground execution goes through the wired ShellRunner engine. Production
        # always wires bash (build_kernel unconditionally calls wire_background_tasks),
        # so wiring is required here — the former no-wiring `_run_legacy_sync` /
        # BashRunner path was a dead second engine and was deleted in bugfix-417-M4
        # (decision 8). _require_wiring raises a clear ToolError if a caller somehow
        # constructed BashTool without wiring.
        return self._run_foreground(
            command=command,
            description=description,
            timeout_value=timeout_value,
            ctx=ctx,
        )

    # ------------------------------------------------------------------
    # Background launch
    # ------------------------------------------------------------------

    def _run_background(
        self,
        *,
        command: str,
        description: str,
        timeout_value: float | None,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        wiring = self._require_wiring()
        registry = wiring.registry

        task_id = generate_bash_task_id()
        parent_session_id = ctx.session_id or ""
        effective_description = description or command[:50]

        output_file = wiring.output.open(parent_session_id, task_id)

        registry.register_bash(
            task_id=task_id,
            parent_session_id=parent_session_id,
            description=effective_description,
            command=command,
            output_file=str(output_file),
            workspace_root=str(ctx.repo_root),
        )
        registry.mark_running(task_id)

        stopper = wiring.bash_runner.start(
            command=command,
            cwd=ctx.cwd,
            output=wiring.output,
            task_id=task_id,
            timeout=timeout_value,
            on_complete=_make_bash_on_complete(registry, task_id),
            on_fail=_make_bash_on_fail(registry, task_id),
        )
        registry.set_stop_handle(task_id, stopper)

        return {
            "status": "async_launched",
            "task_id": task_id,
            "description": effective_description,
            "output_file": str(output_file),
        }

    # ------------------------------------------------------------------
    # Foreground with auto-background
    # ------------------------------------------------------------------

    def _run_foreground(
        self,
        *,
        command: str,
        description: str,
        timeout_value: float | None,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        wiring = self._require_wiring()
        registry = wiring.registry

        task_id = generate_bash_task_id()
        parent_session_id = ctx.session_id or ""
        effective_description = description or command[:50]

        output_file = wiring.output.open(parent_session_id, task_id)

        completed_event = threading.Event()
        result_holder: dict[str, Any] = {}

        def on_complete(
            *,
            task_id: str,
            result_text: str | None,
            usage: Mapping[str, Any] | None,
            duration_ms: int,
            tool_use_count: int,
        ) -> None:
            # For foreground tasks, suppress the background notification: the result is
            # delivered synchronously via completed_event rather than via notification.
            # For auto-backgrounded tasks (foreground budget exceeded), is_foreground is False
            # so notification is not suppressed.
            is_foreground = not result_holder.get("backgrounded", False)
            registry.complete(
                task_id,
                result_text=result_text,
                usage=usage,
                duration_ms=duration_ms,
                tool_use_count=tool_use_count,
                notified=is_foreground,
            )
            result_holder["status"] = "completed"
            completed_event.set()

        def on_fail(*, task_id: str, error: str) -> None:
            registry.fail(task_id, error=error)
            result_holder["status"] = "failed"
            result_holder["error"] = error
            completed_event.set()

        registry.register_bash(
            task_id=task_id,
            parent_session_id=parent_session_id,
            description=effective_description,
            command=command,
            output_file=str(output_file),
            workspace_root=str(ctx.repo_root),
        )
        registry.mark_running(task_id)

        stopper = wiring.bash_runner.start(
            command=command,
            cwd=ctx.cwd,
            output=wiring.output,
            task_id=task_id,
            timeout=timeout_value,
            on_complete=on_complete,
            on_fail=on_fail,
        )

        # bugfix-417-M5 (#114): on /stop the runner's _monitor takes the silent
        # `_stopped` path (designed for background task_stop, which has no waiter)
        # and never sets completed_event. The foreground worker below is blocked on
        # completed_event.wait(budget), so killing the subprocess alone would leave
        # this to_thread worker parked until the 120s budget — a thread leak. Wrap
        # the runner stopper so stopping ALSO wakes this waiter immediately with an
        # interrupted result: the worker returns promptly, the run unwinds, and the
        # orphaned tool_call is recovered as "interrupted" (no 120s lingering).
        class _ForegroundStopper:
            def stop(self) -> None:
                stopper.stop()  # killpg the subprocess tree (M4-hardened)
                result_holder["status"] = "interrupted"
                completed_event.set()

        # foreground=True so interrupt/cancel can reap THIS subprocess tree (the
        # run is blocked inside the to_thread below until the process is killed),
        # while leaving user-launched background tasks alone (bugfix-417-M5, #114).
        registry.set_stop_handle(task_id, _ForegroundStopper(), foreground=True)

        # Wait up to the foreground budget for completion, polling at the heartbeat
        # interval so we can emit a phase:running liveness event each tick. This is
        # the bash liveness source: the executor (tools/registry) bridges
        # ctx.emit_execution_event from this to_thread worker back to its async loop
        # via run_coroutine_threadsafe (M3 R1), where realtime_stream projects it to a
        # run_heartbeat that resets both watchdogs (bugfix-417-M4: prior to this the
        # production foreground path produced zero events for the whole run, so a
        # silent long command was reaped as a stall — B1).
        start_monotonic = time.monotonic()
        completed = False
        while True:
            elapsed = time.monotonic() - start_monotonic
            remaining = _DEFAULT_FOREGROUND_BUDGET - elapsed
            if remaining <= 0:
                break
            if completed_event.wait(
                timeout=min(_FOREGROUND_HEARTBEAT_INTERVAL, remaining)
            ):
                completed = True
                break
            ctx.emit_execution_event(
                {
                    "phase": "running",
                    "status": "running",
                    "elapsed_ms": int((time.monotonic() - start_monotonic) * 1000),
                    "command": command,
                }
            )

        if not completed:
            # Auto-background: allow notification when monitor thread calls on_complete.
            result_holder["backgrounded"] = True
            # The task is no longer run-blocking — demote it from the foreground
            # set so a later /stop does not reap a now-detached background task
            # (bugfix-417-M5, #114).
            registry.set_stop_handle(task_id, stopper, foreground=False)
            return {
                "status": "async_launched",
                "task_id": task_id,
                "description": effective_description,
                "output_file": str(output_file),
            }

        # Command completed within budget — read output and return synchronously.
        stdout = _read_output_file(output_file)

        if result_holder.get("status") == "completed":
            return {
                "stdout": stdout,
                "stderr": "",
                "exitCode": 0,
                "truncated": False,
            }

        # bugfix-417-M5 (#114): stopped by interrupt/cancel. Return promptly with a
        # benign interrupted result so this to_thread worker does not linger to the
        # 120s budget. The carrier Task is also force-cancelled by the registry, so
        # this return value is typically discarded as the run unwinds via
        # CancelledError; returning (rather than raising) just avoids a spurious
        # error if the worker happens to outrace the cancel.
        if result_holder.get("status") == "interrupted":
            return {
                "stdout": stdout,
                "stderr": "",
                "exitCode": 130,
                "truncated": False,
                "interrupted": True,
                "reason_code": "interrupted",
            }

        # Failed within budget.
        error = result_holder.get("error", "command failed")

        # bugfix-417-M4 R2 (decision 5): the command hit its OWN deadline — ShellRunner
        # reports this via on_fail(error="timed out after Xs"). Classify the badge as
        # "执行超时" (tool_timeout), distinct from a watchdog liveness stall ("已中断"/
        # stalled). reason_code is lifted into the ToolResult by StreamingToolExecutor
        # and rendered as the tool_end badge. Prior to M4 only the dead _run_legacy_sync
        # set this, so production timeouts surfaced reason=null (C1).
        if error.startswith("timed out after"):
            timeout_seconds = _resolve_timeout_seconds(None, timeout_value)
            raise ToolError(
                _render_error_message(
                    content=stdout,
                    suffix=f"Command timed out after {_format_timeout_seconds(timeout_seconds)} seconds",
                ),
                tool_name=self.name,
                details={
                    "exitCode": 124,
                    "exit_code": 124,
                    "content": stdout,
                    "truncated": False,
                    "timedOut": True,
                    "timed_out": True,
                    "timeout": timeout_seconds,
                    "reason_code": "tool_timeout",
                },
            )

        exit_code = _parse_exit_code_from_error(error)

        details: dict[str, Any] = {
            "exitCode": exit_code,
            "exit_code": exit_code,
            "content": stdout,
            "truncated": False,
        }
        if exit_code < 0:
            signal_number = -exit_code
            try:
                signal_name = signal.Signals(signal_number).name
            except ValueError:
                signal_name = f"SIG{signal_number}"
            details["signal"] = signal_name
            details["signalNumber"] = signal_number
            details["signal_number"] = signal_number

        raise ToolError(
            _render_error_message(
                content=stdout,
                suffix=f"Command exited with code {exit_code}",
            ),
            tool_name=self.name,
            details=details,
        )

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        if error is not None:
            return error
        if not isinstance(output, Mapping):
            return json_serialize(output)

        # Background task receipt
        if output.get("status") == "async_launched":
            lines = [
                "Background command launched.",
                "",
                f"task_id: {output.get('task_id', '')}",
            ]
            if output.get("description"):
                lines.append(f"description: {output['description']}")
            lines.extend(
                [
                    "status: running",
                    f"output_file: {output.get('output_file', '')}",
                    "",
                    "The command is running in the background. You will be notified automatically when it completes.",
                    "Use Read on output_file to inspect progress or final output.",
                    f'Use task_stop with task_id="{output.get("task_id", "")}" to stop it.',
                ]
            )
            return "\n".join(lines)

        stdout = output.get("stdout", "") or ""

        if stdout:
            stdout = stdout.lstrip("\n")
            stdout = stdout.rstrip()

        return stdout or "(no output)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------


def _make_bash_on_complete(registry: Any, task_id: str) -> Any:
    def _on_complete(
        *,
        task_id: str,
        result_text: str | None,
        usage: Mapping[str, Any] | None,
        duration_ms: int,
        tool_use_count: int,
    ) -> None:
        registry.complete(
            task_id,
            result_text=result_text,
            usage=usage,
            duration_ms=duration_ms,
            tool_use_count=tool_use_count,
        )

    return _on_complete


def _make_bash_on_fail(registry: Any, task_id: str) -> Any:
    def _on_fail(*, task_id: str, error: str) -> None:
        registry.fail(task_id, error=error)

    return _on_fail


def _read_output_file(path: Path) -> str:
    """Read output file, stripping the background-task header line if present."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    lines = text.splitlines()
    if lines and lines[0].startswith("# Background task "):
        lines = lines[1:]
    return "\n".join(lines)


def _parse_exit_code_from_error(error: str) -> int:
    """Best-effort parse of exit code from shell runner error strings."""
    if error.startswith("exit code "):
        try:
            return int(error[len("exit code ") :])
        except ValueError:
            pass
    if error.startswith("timed out after "):
        return 124  # Standard timeout exit code
    return 1


def _render_error_message(*, content: str, suffix: str) -> str:
    if not content:
        return suffix
    return f"{content}\n\n{suffix}"


def _resolve_timeout_seconds(primary: Any, fallback: float | None) -> float:
    if isinstance(primary, int | float):
        return float(primary)
    if fallback is not None:
        return fallback
    return 0.0


def _format_timeout_seconds(timeout_seconds: float) -> str:
    return f"{timeout_seconds:g}"
