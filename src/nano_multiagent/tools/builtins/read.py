"""Built-in `read` tool for bounded text and image loading."""

import base64
from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.core.errors import ToolError

from ..base import ToolContext

_IMAGE_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class ReadTool:
    """Read UTF-8 text with pagination or inline supported image formats."""

    name = "read"
    description = "Read text files and images with offset/limit and output truncation."
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
        """Read file content while enforcing sandbox paths and output limits."""

        raw_path = str(args["path"])
        file_path = ctx.safety.resolve_read_path(raw_path, cwd=ctx.cwd, tool_name=self.name)

        if not file_path.exists() or not file_path.is_file():
            raise ToolError(
                "file does not exist",
                tool_name=self.name,
                details={"path": raw_path},
            )

        mime_type = _image_mime_type(file_path)
        if mime_type is not None:
            image_bytes = file_path.read_bytes()
            encoded = base64.b64encode(image_bytes).decode("ascii")
            display_path = _display_path(file_path, ctx.repo_root)
            return {
                "path": display_path,
                "offset": 1,
                "next_offset": None,
                "total_lines": 0,
                "truncated": False,
                "content": [
                    {
                        "type": "text",
                        "text": f"Image: {display_path} ({mime_type}, {len(image_bytes)} bytes)",
                    },
                    {
                        "type": "image",
                        "mime_type": mime_type,
                        "image_url": f"data:{mime_type};base64,{encoded}",
                    },
                ],
            }

        offset = int(args.get("offset", 1))
        if offset < 1:
            raise ToolError("offset must be >= 1", tool_name=self.name)

        limit = args.get("limit")
        if limit is not None:
            limit = int(limit)
            if limit < 1:
                raise ToolError("limit must be >= 1", tool_name=self.name)

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(
                "file is not UTF-8 text; read supports text and jpg/png/gif/webp images",
                tool_name=self.name,
                details={"path": raw_path},
            ) from exc
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
            if truncated and selected:
                rendered = (
                    "Output omitted because at least one line exceeds the byte limit. "
                    "Use `bash`/`sed` with explicit ranges to inspect this file."
                )
                next_offset = offset
            else:
                next_offset = None
        else:
            candidate_offset = offset + returned_lines
            next_offset = candidate_offset if total_lines == 0 or candidate_offset <= total_lines else None
        if truncated and next_offset is not None:
            hint = f"[output truncated; continue with offset={next_offset}]"
            rendered = f"{rendered}\n\n{hint}" if rendered else hint

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


def _image_mime_type(path: Path) -> str | None:
    return _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())
