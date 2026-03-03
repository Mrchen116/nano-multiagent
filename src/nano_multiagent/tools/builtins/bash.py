"""Built-in `bash` tool with policy and output guardrails."""

import signal
from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError

from ..base import ToolContext


class BashTool:
    """Execute shell commands within `ToolSafety` command and timeout policy."""

    name = "bash"
    description = "Execute a bash command under safety guardrails."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "number"},
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

        execution = ctx.safety.run_command(
            command=command,
            cwd=ctx.cwd,
            timeout=timeout_value,
            tool_name=self.name,
        )

        if execution.exit_code != 0:
            details: dict[str, Any] = {
                "exit_code": execution.exit_code,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "truncated": execution.truncated,
            }
            if execution.full_output_path is not None:
                details["full_output_path"] = execution.full_output_path
            if execution.exit_code < 0:
                signal_number = -execution.exit_code
                try:
                    signal_name = signal.Signals(signal_number).name
                except ValueError:
                    signal_name = f"SIG{signal_number}"
                details["signal"] = signal_name
                details["signal_number"] = signal_number
                raise ToolError(
                    f"command terminated by signal {signal_name} ({signal_number})",
                    tool_name=self.name,
                    details=details,
                )
            raise ToolError(
                f"command exited with non-zero status: {execution.exit_code}",
                tool_name=self.name,
                details=details,
            )

        result: dict[str, Any] = {
            "command": command,
            "exit_code": execution.exit_code,
            "stdout": execution.stdout,
            "stderr": execution.stderr,
            "truncated": execution.truncated,
        }
        if execution.full_output_path is not None:
            result["full_output_path"] = execution.full_output_path
        return result
