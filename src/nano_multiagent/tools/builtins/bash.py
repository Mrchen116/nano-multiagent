from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError

from ..base import ToolContext


class BashTool:
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
            raise ToolError(
                f"command exited with non-zero status: {execution.exit_code}",
                tool_name=self.name,
                details={
                    "exit_code": execution.exit_code,
                    "stdout": execution.stdout,
                    "stderr": execution.stderr,
                    "truncated": execution.truncated,
                },
            )

        return {
            "command": command,
            "exit_code": execution.exit_code,
            "stdout": execution.stdout,
            "stderr": execution.stderr,
            "truncated": execution.truncated,
        }
