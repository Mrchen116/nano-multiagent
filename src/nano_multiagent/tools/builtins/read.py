from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError

from ..base import ToolContext


class ReadTool:
    name = "read"
    description = "Read text files with offset/limit and output truncation."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        raw_path = str(args["path"])
        file_path = ctx.safety.resolve_read_path(raw_path, cwd=ctx.cwd, tool_name=self.name)

        if not file_path.exists() or not file_path.is_file():
            raise ToolError(
                "file does not exist",
                tool_name=self.name,
                details={"path": raw_path},
            )

        offset = int(args.get("offset", 1))
        if offset < 1:
            raise ToolError("offset must be >= 1", tool_name=self.name)

        limit = args.get("limit")
        if limit is not None:
            limit = int(limit)
            if limit < 1:
                raise ToolError("limit must be >= 1", tool_name=self.name)

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        total_lines = len(lines)

        if total_lines > 0 and offset > total_lines:
            raise ToolError(
                "offset is out of range",
                tool_name=self.name,
                details={"offset": offset, "total_lines": total_lines},
            )

        start_index = max(0, offset - 1)
        selected = lines[start_index:]
        if limit is not None:
            selected = selected[:limit]

        rendered, truncated = ctx.safety.truncate_text(
            "\n".join(selected),
            max_lines=ctx.safety.config.read_max_lines,
            max_bytes=ctx.safety.config.read_max_bytes,
            tail=False,
        )

        returned_lines = len(rendered.splitlines()) if rendered else 0
        next_offset: int | None
        if returned_lines == 0:
            next_offset = None
        else:
            candidate_offset = offset + returned_lines
            next_offset = candidate_offset if total_lines == 0 or candidate_offset <= total_lines else None

        return {
            "path": _display_path(file_path, ctx.repo_root),
            "offset": offset,
            "next_offset": next_offset,
            "total_lines": total_lines,
            "truncated": truncated,
            "content": rendered,
        }


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
