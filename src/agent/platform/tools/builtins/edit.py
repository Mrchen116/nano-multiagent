"""Built-in `edit` tool for one-shot exact text replacement."""

import difflib
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.permissions.broker import PermissionDecision
from agent.platform.tools.dangerous_paths import check_dangerous_path
from agent.platform.tools.presentation import (
    ToolPresentationEvent,
    _enforce_cap,
    display_path as _display_path,
)


# ---------------------------------------------------------------------------
# Presenter (feat-425 决策 3: presentation travels with the tool — class here)
# ---------------------------------------------------------------------------


class _EditPresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="Edit",
            summary=str(args.get("path", "")),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        path = str(args.get("path", ""))
        old_text = str(args.get("oldText", ""))
        new_text = str(args.get("newText", ""))
        error = getattr(result, "error", None)
        if error:
            # feat-409 failalign: 失败态 summary = 干净主参数(path),不含 error 文本。
            # detail 只放 error(path 已在折叠行 summary),走前端 ErrorCard 渲染一次。
            return ToolPresentationEvent(
                visible=True,
                label="Edit",
                summary=path or "failed",
                detail={"error": {"message": str(error)}},
            )
        # compute a minimal unified diff
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        if not old_lines:
            old_lines = [old_text]
        if not new_lines:
            new_lines = [new_text]
        diff = "".join(
            difflib.unified_diff(
                old_lines, new_lines, fromfile=path, tofile=path, lineterm=""
            )
        )
        # find first changed line number (best-effort)
        first_changed_line: int | None = None
        for i, (o, n) in enumerate(zip(old_lines, new_lines), start=1):
            if o != n:
                first_changed_line = i
                break
        if first_changed_line is None and len(old_lines) != len(new_lines):
            first_changed_line = min(len(old_lines), len(new_lines)) + 1
        detail = _enforce_cap(
            {
                "path": path,
                "diff": diff,
                "firstChangedLine": first_changed_line,
                "truncated": False,
            }
        )
        line_info = f" (line {first_changed_line})" if first_changed_line else ""
        return ToolPresentationEvent(
            visible=True,
            label="Edit",
            summary=f"updated{line_info}",
            detail=detail,
        )


_EDIT_PRESENTER = _EditPresenter()


class EditTool:
    """Replace exactly one text match in a file inside the sandbox."""

    name = "edit"
    presenter = _EDIT_PRESENTER  # 决策 12: presentation travels with the tool object
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
            "path": {
                "type": "string",
                "description": "Path to the file to edit (relative or absolute)",
            },
            "oldText": {
                "type": "string",
                "description": "Exact text to find and replace (must match exactly)",
            },
            "newText": {
                "type": "string",
                "description": "New text to replace the old text with",
            },
        },
        "required": ["path", "oldText", "newText"],
        "additionalProperties": False,
    }

    def check_permissions(
        self, tool_input: Mapping[str, Any], ctx: Any
    ) -> PermissionDecision:
        """Guard edits to dangerous system files/directories (D5, bugfix-355).

        Same semantics as WriteTool.check_permissions — returns ask + safety_check
        so auto_mode_gate treats this as bypass-immune (W1).

        ctx may be a ToolContext (tool body) or a HookContext (gate pre-check).
        Uses ctx.cwd when available, falls back to ctx.repo_root (R2-#1 fix).
        """
        raw_path = str(tool_input.get("path", ""))
        cwd = getattr(ctx, "cwd", None) or getattr(ctx, "repo_root", None)
        if check_dangerous_path(raw_path, cwd=cwd):
            return PermissionDecision(
                behavior="ask",
                decision_reason={"type": "safety_check", "matched_path": raw_path},
                reason=(
                    f"Editing {raw_path} requires explicit confirmation "
                    "(sensitive system file or directory)"
                ),
            )
        return PermissionDecision(behavior="passthrough")

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Apply one deterministic replacement and return changed line metadata."""

        raw_path = str(args["path"])
        old_text = str(args["oldText"])
        new_text = str(args["newText"])

        if not old_text:
            raise ToolError("oldText cannot be empty", tool_name=self.name)

        file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
        if not file_path.exists() or not file_path.is_file():
            raise ToolError(
                "file does not exist", tool_name=self.name, details={"path": raw_path}
            )

        display_path = _display_path(file_path, ctx.repo_root)

        # -- Read-Before-Write enforcement (always checked for edits) --
        if ctx.session_file_state is not None:
            can_write, error_code = ctx.session_file_state.can_write(
                str(file_path.resolve())
            )
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
            raise ToolError(
                "Could not find the exact text to replace", tool_name=self.name
            )
        if matches > 1:
            raise ToolError(
                "Found multiple matches; text must be unique", tool_name=self.name
            )

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
