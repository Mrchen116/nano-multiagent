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

# Foreground budget before auto-backgrounding (seconds)
_DEFAULT_FOREGROUND_BUDGET = 120.0

_READ_ONLY_COMMANDS = frozenset({
    "ls", "cat", "grep", "rg", "find", "head", "tail", "echo", "pwd", "wc",
    "file", "stat", "readlink", "sort", "uniq", "cut", "tr", "which", "whoami",
    "id", "uname", "date", "ps", "df", "du", "env", "printenv", "hostname",
})

_READ_ONLY_GIT_SUBCOMMANDS = frozenset({
    "status", "log", "diff", "show", "branch", "remote", "config", "rev-parse",
    "ls-files", "blame", "stash", "tag", "describe",
})


class BashTool:
    """Execute shell commands within `ToolSafety` command and timeout policy.

    Supports synchronous execution (default), explicit background execution
    (``run_in_background=true``), and automatic backgrounding when a
    foreground command exceeds the 15-second budget.
    """

    name = "bash"
    is_concurrency_safe = False
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
            "timeout": {"type": "number", "description": "Timeout in seconds (optional, no default timeout)"},
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

    def bind_wiring(self, wiring: Any | None) -> None:
        """Bind background task wiring after bootstrap."""
        self._wiring = wiring

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

        # Foreground: use background-aware path when wiring is available,
        # otherwise fall back to the legacy synchronous path.
        if self._wiring is not None:
            return self._run_foreground(
                command=command,
                description=description,
                timeout_value=timeout_value,
                ctx=ctx,
            )
        return self._run_legacy_sync(
            command=command,
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

        record = registry.register_bash(
            task_id=task_id,
            parent_session_id=parent_session_id,
            description=effective_description,
            command=command,
            output_file=str(output_file),
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

        def on_complete(*, task_id: str, result_text: str | None, usage: Mapping[str, Any] | None, duration_ms: int, tool_use_count: int) -> None:
            registry.complete(
                task_id,
                result_text=result_text,
                usage=usage,
                duration_ms=duration_ms,
                tool_use_count=tool_use_count,
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
        registry.set_stop_handle(task_id, stopper)

        # Wait up to the foreground budget for completion.
        completed = completed_event.wait(timeout=_DEFAULT_FOREGROUND_BUDGET)

        if not completed:
            # Auto-background: process keeps running, monitor thread will update registry.
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

        # Failed within budget.
        error = result_holder.get("error", "command failed")
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

    # ------------------------------------------------------------------
    # Legacy synchronous path (used when wiring is not available)
    # ------------------------------------------------------------------

    def _run_legacy_sync(
        self,
        *,
        command: str,
        timeout_value: float | None,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        def _on_execution_event(payload: Mapping[str, Any]) -> None:
            event_payload: dict[str, Any] = dict(payload)
            event_payload.setdefault("command", command)
            ctx.emit_execution_event(event_payload)

        try:
            execution = ctx.safety.run_command_stream(
                command=command,
                cwd=ctx.cwd,
                timeout=timeout_value,
                tool_name=self.name,
                allow_unlisted=bool(ctx.safety_overrides.get("bash_allow_unlisted")),
                on_event=_on_execution_event,
                heartbeat_interval=0.1,
            )
        except ToolError as exc:
            if bool(exc.details.get("aborted")):
                raise ToolError(
                    "Command aborted",
                    tool_name=self.name,
                    details={"aborted": True},
                ) from exc
            if bool(exc.details.get("timedOut") or exc.details.get("timed_out")):
                timeout_detail = _resolve_timeout_seconds(
                    exc.details.get("timeout"),
                    timeout_value,
                )
                raise ToolError(
                    f"Command timed out after {_format_timeout_seconds(timeout_detail)} seconds",
                    tool_name=self.name,
                    details={
                        "timedOut": True,
                        "timed_out": True,
                        "timeout": timeout_detail,
                        "content": str(exc.details.get("content", "")),
                        "truncated": bool(exc.details.get("truncated", False)),
                    },
                ) from exc
            raise

        stdout = ""
        if execution.output_file_path:
            file_path = Path(execution.output_file_path)
            if file_path.exists():
                stdout = file_path.read_text(encoding="utf-8")
                file_path.unlink(missing_ok=True)
        elif execution.text:
            stdout = execution.text

        if execution.aborted:
            raise ToolError(
                _render_error_message(content=stdout, suffix="Command aborted"),
                tool_name=self.name,
                details=_build_error_details(execution, stdout),
            )

        if execution.timed_out:
            timeout_seconds = _resolve_timeout_seconds(execution.timeout, timeout_value)
            raise ToolError(
                _render_error_message(
                    content=stdout,
                    suffix=f"Command timed out after {_format_timeout_seconds(timeout_seconds)} seconds",
                ),
                tool_name=self.name,
                details={
                    **_build_error_details(execution, stdout),
                    "timedOut": True,
                    "timed_out": True,
                    "timeout": timeout_seconds,
                },
            )

        if execution.exit_code != 0:
            details = _build_error_details(execution, stdout)
            if execution.exit_code < 0:
                signal_number = -execution.exit_code
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
                    suffix=f"Command exited with code {execution.exit_code}",
                ),
                tool_name=self.name,
                details=details,
            )

        result: dict[str, Any] = {
            "stdout": stdout,
            "stderr": "",
            "exitCode": execution.exit_code,
            "truncated": execution.truncated,
        }
        if execution.output_file_path:
            result["fullOutputPath"] = execution.output_file_path
        return result

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
            lines.extend([
                "status: running",
                f"output_file: {output.get('output_file', '')}",
                "",
                "The command is running in the background. You will be notified automatically when it completes.",
                "Use Read on output_file to inspect progress or final output.",
                f'Use task_stop with task_id="{output.get("task_id", "")}" to stop it.',
            ])
            return "\n".join(lines)

        stdout = output.get("stdout", "") or ""

        if stdout:
            stdout = stdout.lstrip("\n")
            stdout = stdout.rstrip()

        return stdout or "(no output)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_wiring(self) -> Any:
        if self._wiring is None:
            raise ToolError("background task wiring is not configured", tool_name=self.name)
        return self._wiring


def _make_bash_on_complete(registry: Any, task_id: str) -> Any:
    def _on_complete(*, task_id: str, result_text: str | None, usage: Mapping[str, Any] | None, duration_ms: int, tool_use_count: int) -> None:
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
            return int(error[len("exit code "):])
        except ValueError:
            pass
    if error.startswith("timed out after "):
        return 124  # Standard timeout exit code
    return 1


def _render_error_message(*, content: str, suffix: str) -> str:
    if not content:
        return suffix
    return f"{content}\n\n{suffix}"


def _build_error_details(execution: Any, stdout: str) -> dict[str, Any]:
    details: dict[str, Any] = {
        "exitCode": execution.exit_code,
        "exit_code": execution.exit_code,
        "content": stdout,
        "truncated": execution.truncated,
    }
    return details


def _resolve_timeout_seconds(primary: Any, fallback: float | None) -> float:
    if isinstance(primary, int | float):
        return float(primary)
    if fallback is not None:
        return fallback
    return 0.0


def _format_timeout_seconds(timeout_seconds: float) -> str:
    return f"{timeout_seconds:g}"
