from pathlib import Path
from typing import Any, Mapping

from ..base import ToolContext


class WriteTool:
    name = "write"
    description = "Write content to a file (create or overwrite) with sandbox checks."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        raw_path = str(args["path"])
        content = str(args["content"])
        file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
        existed_before = file_path.exists()

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return {
            "path": _display_path(file_path, ctx.repo_root),
            "bytes_written": len(content.encode("utf-8")),
            "overwritten": existed_before,
        }


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
