"""Built-in `write` tool for sandboxed file creation and overwrite."""

from pathlib import Path
from typing import Any, Mapping

from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize


class WriteTool:
    """Write full file content and report overwrite metadata."""

    name = "write"
    is_concurrency_safe = False
    description = (
        "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
        "Automatically creates parent directories."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write (relative or absolute)"},
            "content": {"type": "string", "description": "Content to write to the file"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Write UTF-8 content to a resolved sandbox path."""

        raw_path = str(args["path"])
        content = str(args["content"])
        file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        display_path = _display_path(file_path, ctx.repo_root)
        byte_count = len(content.encode("utf-8"))

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully wrote {byte_count} bytes to {display_path}",
                }
            ]
        }

    def serialize_result(self, output: Any) -> str:
        return json_serialize(output)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
