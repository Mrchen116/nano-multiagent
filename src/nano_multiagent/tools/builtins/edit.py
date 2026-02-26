from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError

from ..base import ToolContext


class EditTool:
    name = "edit"
    description = "Edit a file by replacing exact text once."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "oldText": {"type": "string"},
            "newText": {"type": "string"},
        },
        "required": ["path", "oldText", "newText"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        raw_path = str(args["path"])
        old_text = str(args["oldText"])
        new_text = str(args["newText"])

        if not old_text:
            raise ToolError("oldText cannot be empty", tool_name=self.name)

        file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
        if not file_path.exists() or not file_path.is_file():
            raise ToolError("file does not exist", tool_name=self.name, details={"path": raw_path})

        source = file_path.read_text(encoding="utf-8")
        matches = source.count(old_text)
        if matches == 0:
            raise ToolError("oldText not found", tool_name=self.name)
        if matches > 1:
            raise ToolError("multiple matches found; edit requires unique match", tool_name=self.name)

        updated = source.replace(old_text, new_text, 1)
        if updated == source:
            raise ToolError("edit produced no changes", tool_name=self.name)

        file_path.write_text(updated, encoding="utf-8")
        first_offset = source.index(old_text)
        first_changed_line = source[:first_offset].count("\n") + 1

        return {
            "path": _display_path(file_path, ctx.repo_root),
            "replaced": 1,
            "first_changed_line": first_changed_line,
        }


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
