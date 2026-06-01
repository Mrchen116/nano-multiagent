"""Built-in `write` tool for sandboxed file creation and overwrite."""

from pathlib import Path
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.permissions.broker import PermissionDecision
from agent.platform.tools.dangerous_paths import check_dangerous_path


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
            "path": {
                "type": "string",
                "description": "Path to the file to write (relative or absolute)",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def check_permissions(
        self, tool_input: Mapping[str, Any], ctx: Any
    ) -> PermissionDecision:
        """Guard writes to dangerous system files/directories (D5, bugfix-355).

        Matches against DANGEROUS_FILES (basename) and DANGEROUS_DIRECTORIES (any segment).
        Returns ask + decision_reason.type='safety_check' so auto_mode_gate treats this
        as bypass-immune — even dangerously_skip_permissions mode cannot auto-approve.

        ctx may be a ToolContext (tool body execution) or a HookContext (gate pre-check).
        Both carry repo_root; ToolContext also has cwd. We use cwd when available and fall
        back to repo_root so relative paths can be resolved in both call sites.
        """
        raw_path = str(tool_input.get("path", ""))
        # Resolve cwd: prefer ctx.cwd (ToolContext), fall back to ctx.repo_root (HookContext).
        # This dual-ctx support avoids AttributeError when gate passes HookContext (R2-#1 fix).
        cwd = getattr(ctx, "cwd", None) or getattr(ctx, "repo_root", None)
        if check_dangerous_path(raw_path, cwd=cwd):
            return PermissionDecision(
                behavior="ask",
                decision_reason={"type": "safety_check", "matched_path": raw_path},
                reason=(
                    f"Writing to {raw_path} requires explicit confirmation "
                    "(sensitive system file or directory)"
                ),
            )
        return PermissionDecision(behavior="passthrough")

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Write UTF-8 content to a resolved sandbox path."""

        raw_path = str(args["path"])
        content = str(args["content"])
        file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
        file_exists = file_path.exists()
        display_path = _display_path(file_path, ctx.repo_root)

        # -- Read-Before-Write enforcement (only when overwriting existing file) --
        if file_exists and ctx.session_file_state is not None:
            can_write, error_code = ctx.session_file_state.can_write(
                str(file_path.resolve())
            )
            if not can_write:
                if error_code == 6:
                    raise ToolError(
                        f"Cannot overwrite {display_path} because it has not been read yet. "
                        "Please read the file first to ensure you are aware of its current contents.",
                        tool_name=self.name,
                        details={"errorCode": 6, "filePath": display_path},
                    )
                elif error_code == 7:
                    raise ToolError(
                        f"Cannot overwrite {display_path} because it was modified externally "
                        "since it was last read. Please re-read the file to get the latest contents.",
                        tool_name=self.name,
                        details={"errorCode": 7, "filePath": display_path},
                    )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

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
            "type": "update" if file_exists else "create",
            "filePath": str(file_path),
            "displayPath": display_path,
        }

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        if error is not None:
            return error
        if not isinstance(output, Mapping):
            return json_serialize(output)

        file_path = output.get("displayPath", output.get("filePath", "unknown"))
        write_type = output.get("type")

        if write_type == "create":
            return f"File created successfully at: {file_path}"
        elif write_type == "update":
            return f"The file {file_path} has been updated successfully."
        else:
            return json_serialize(output)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
