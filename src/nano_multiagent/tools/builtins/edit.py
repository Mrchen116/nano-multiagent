"""Built-in `edit` tool for one-shot exact text replacement."""

import difflib
from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError

from ..base import ToolContext


class EditTool:
    """Replace exactly one text match in a file inside the sandbox."""

    name = "edit"
    description = (
        "Edit a file by replacing exact text. The oldText must match exactly (including whitespace). "
        "Use this for precise, surgical edits."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to edit (relative or absolute)"},
            "oldText": {"type": "string", "description": "Exact text to find and replace (must match exactly)"},
            "newText": {"type": "string", "description": "New text to replace the old text with"},
        },
        "required": ["path", "oldText", "newText"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Apply one deterministic replacement and return changed line metadata."""

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
            raise ToolError("Could not find the exact text to replace", tool_name=self.name)
        if matches > 1:
            raise ToolError("Found multiple matches; text must be unique", tool_name=self.name)

        updated = source.replace(old_text, new_text, 1)
        if updated == source:
            raise ToolError("No changes made", tool_name=self.name)

        file_path.write_text(updated, encoding="utf-8")
        display_path = _display_path(file_path, ctx.repo_root)
        first_offset = source.index(old_text)
        first_changed_line = source[:first_offset].count("\n") + 1
        diff = "\n".join(
            difflib.unified_diff(
                source.splitlines(),
                updated.splitlines(),
                fromfile=f"a/{display_path}",
                tofile=f"b/{display_path}",
                lineterm="",
            )
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully replaced text in {display_path}.",
                }
            ],
            "details": {
                "diff": diff,
                "firstChangedLine": first_changed_line,
            },
        }


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
