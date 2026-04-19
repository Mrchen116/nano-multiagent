"""Built-in `edit` tool for one-shot exact text replacement."""

import difflib
from pathlib import Path
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize


class EditTool:
    """Replace exactly one text match in a file inside the sandbox."""

    name = "edit"
    is_concurrency_safe = False
    description = (
        "Edit a file by replacing exact text. The oldText must match exactly (including whitespace). "
        "Use this for precise, surgical edits. "
        "When editing text from Read tool output, ensure you preserve the exact indentation "
        "(tabs/spaces) as it appears AFTER the line number prefix. "
        "The line number prefix format is: 6 spaces + line number + →. "
        "Everything after that is the actual file content to match. "
        "Never include any part of the line number prefix in the oldText or newText."
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

        display_path = _display_path(file_path, ctx.repo_root)

        # -- Read-Before-Write enforcement (always checked for edits) --
        if ctx.session_file_state is not None:
            can_write, error_code = ctx.session_file_state.can_write(str(file_path.resolve()))
            if not can_write:
                if error_code == 6:
                    raise ToolError(
                        f"Cannot edit {display_path} because it has not been read yet. "
                        "Please read the file first to ensure you are aware of its current contents.",
                        tool_name=self.name,
                        details={"errorCode": 6, "filePath": display_path},
                    )
                elif error_code == 7:
                    raise ToolError(
                        f"Cannot edit {display_path} because it was modified externally "
                        "since it was last read. Please re-read the file to get the latest contents.",
                        tool_name=self.name,
                        details={"errorCode": 7, "filePath": display_path},
                    )

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

        # Update session file state to prevent self-edit stale false positives.
        if ctx.session_file_state is not None:
            try:
                stat = file_path.stat()
                ctx.session_file_state.record_write(
                    file_path=str(file_path.resolve()),
                    mtime_ns=stat.st_mtime_ns,
                    size=stat.st_size,
                )
            except (OSError, ValueError):
                pass

        return {
            "filePath": str(file_path),
            "displayPath": display_path,
            "replaceAll": False,
            "details": {
                "diff": diff,
                "firstChangedLine": first_changed_line,
            },
        }

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        if error is not None:
            return error
        if not isinstance(output, Mapping):
            return json_serialize(output)

        file_path = output.get("displayPath", output.get("filePath", "unknown"))
        if output.get("replaceAll"):
            return (
                f"The file {file_path} has been updated. "
                "All occurrences were successfully replaced."
            )
        return f"The file {file_path} has been updated successfully."


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
