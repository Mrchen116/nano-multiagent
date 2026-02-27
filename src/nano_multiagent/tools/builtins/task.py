from typing import Any, Mapping

from ..base import ToolContext


class TaskTool:
    name = "task"
    description = "Run or schedule a local in-process subagent task."
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["blocking", "non_blocking"],
            },
            "prompt": {"type": "string"},
            "session_id": {"type": "string"},
            "category": {"type": "string"},
            "subagent_type": {"type": "string"},
            "idempotency_key": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["mode"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        del ctx
        return {
            "mode": args["mode"],
            "accepted": True,
            "status": "not_implemented",
        }
