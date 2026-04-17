"""Built-in `bash` tool with policy and output guardrails."""

import signal
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.tools.constants import DEFAULT_MAX_KILOBYTES, DEFAULT_MAX_LINES


class BashTool:
    """Execute shell commands within `ToolSafety` command and timeout policy."""

    name = "bash"
    is_concurrency_safe = False
    description = (
        "Execute a bash command in the current working directory. Returns stdout and stderr. "
        f"Output is truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_KILOBYTES}KB "
        "(whichever is hit first). If truncated, full output is saved to a temp file. Optionally "
        "provide a timeout in seconds."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Bash command to execute"},
            "timeout": {"type": "number", "description": "Timeout in seconds (optional, no default timeout)"},
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Run one shell command and normalize non-zero exits into `ToolError`."""

        command = str(args["command"])

        timeout = args.get("timeout")
        timeout_value: float | None = None
        if timeout is not None:
            timeout_value = float(timeout)
            if timeout_value <= 0:
                raise ToolError("timeout must be > 0", tool_name=self.name)

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

        if execution.aborted:
            raise ToolError(
                _render_error_message(
                    content=execution.text,
                    suffix="Command aborted",
                ),
                tool_name=self.name,
                details=_build_error_details(execution),
            )

        if execution.timed_out:
            timeout_seconds = _resolve_timeout_seconds(execution.timeout, timeout_value)
            raise ToolError(
                _render_error_message(
                    content=execution.text,
                    suffix=f"Command timed out after {_format_timeout_seconds(timeout_seconds)} seconds",
                ),
                tool_name=self.name,
                details={
                    **_build_error_details(execution),
                    "timedOut": True,
                    "timed_out": True,
                    "timeout": timeout_seconds,
                },
            )

        if execution.exit_code != 0:
            details = _build_error_details(execution)
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
                    content=execution.text,
                    suffix=f"Command exited with code {execution.exit_code}",
                ),
                tool_name=self.name,
                details=details,
            )

        result: dict[str, Any] = {
            "command": command,
            "exitCode": execution.exit_code,
            "content": execution.text if execution.text else "(no output)",
            "truncated": execution.truncated,
        }
        if execution.full_output_path is not None:
            result["fullOutputPath"] = execution.full_output_path
        return result

    def serialize_result(self, output: Any) -> str:
        return json_serialize(output)


def _build_error_details(execution: Any) -> dict[str, Any]:
    details: dict[str, Any] = {
        "exitCode": execution.exit_code,
        "exit_code": execution.exit_code,
        "content": execution.text,
        "truncated": execution.truncated,
    }
    if execution.full_output_path is not None:
        details["fullOutputPath"] = execution.full_output_path
        details["full_output_path"] = execution.full_output_path
    return details


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
