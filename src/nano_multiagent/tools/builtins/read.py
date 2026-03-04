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

        truncation = _truncate_head_lines(
            selected,
            max_lines=ctx.safety.config.read_max_lines,
            max_bytes=ctx.safety.config.read_max_bytes,
        )
        rendered = truncation["content"]
        details: dict[str, Any] | None = None
        next_offset: int | None = None

        if truncation["firstLineExceedsLimit"]:
            first_line_size = _format_size(len(selected[0].encode("utf-8")))
            max_bytes_display = _format_size(ctx.safety.config.read_max_bytes)
            rendered = (
                f"[Line {offset} is {first_line_size}, exceeds {max_bytes_display} limit. "
                f"Use bash: sed -n '{offset}p' {raw_path} | head -c {ctx.safety.config.read_max_bytes}]"
            )
            details = {"truncation": truncation}
            next_offset = offset
        elif truncation["truncated"]:
            output_lines = int(truncation["outputLines"])
            end_line = offset + output_lines - 1
            next_offset = end_line + 1
            if truncation["truncatedBy"] == "bytes":
                max_bytes_display = _format_size(ctx.safety.config.read_max_bytes)
                hint = (
                    f"[Showing lines {offset}-{end_line} of {total_lines} "
                    f"({max_bytes_display} limit). Use offset={next_offset} to continue.]"
                )
            else:
                hint = f"[Showing lines {offset}-{end_line} of {total_lines}. Use offset={next_offset} to continue.]"
            rendered = f"{rendered}\n\n{hint}" if rendered else hint
            details = {"truncation": truncation}
        elif limit is not None and start_index + len(selected) < total_lines:
            remaining = total_lines - (start_index + len(selected))
            next_offset = start_index + len(selected) + 1
            rendered = f"{rendered}\n\n[{remaining} more lines in file. Use offset={next_offset} to continue.]"

        response: dict[str, Any] = {
            "path": _display_path(file_path, ctx.repo_root),
            "offset": offset,
            "next_offset": next_offset,
            "total_lines": total_lines,
            "truncated": bool(truncation["truncated"]),
            "content": [{"type": "text", "text": rendered}],
        }
        if details is not None:
            response["details"] = details
        return response


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _image_mime_type(path: Path) -> str | None:
    return _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())


def _format_size(bytes_count: int) -> str:
    if bytes_count < 1024:
        return f"{bytes_count}B"
    if bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f}KB"
    return f"{bytes_count / (1024 * 1024):.1f}MB"


def _truncate_head_lines(lines: list[str], *, max_lines: int, max_bytes: int) -> dict[str, Any]:
    max_lines = max(1, max_lines)
    max_bytes = max(1, max_bytes)

    content = "\n".join(lines)
    total_lines = len(lines)
    total_bytes = len(content.encode("utf-8"))
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return {
            "content": content,
            "truncated": False,
            "truncatedBy": None,
            "totalLines": total_lines,
            "totalBytes": total_bytes,
            "outputLines": total_lines,
            "outputBytes": total_bytes,
            "firstLineExceedsLimit": False,
            "maxLines": max_lines,
            "maxBytes": max_bytes,
        }

    first_line_bytes = len(lines[0].encode("utf-8")) if lines else 0
    if lines and first_line_bytes > max_bytes:
        return {
            "content": "",
            "truncated": True,
            "truncatedBy": "bytes",
            "totalLines": total_lines,
            "totalBytes": total_bytes,
            "outputLines": 0,
            "outputBytes": 0,
            "firstLineExceedsLimit": True,
            "maxLines": max_lines,
            "maxBytes": max_bytes,
        }

    output_lines: list[str] = []
    output_bytes = 0
    truncated_by = "lines"
    for index, line in enumerate(lines):
        if index >= max_lines:
            truncated_by = "lines"
            break
        line_bytes = len(line.encode("utf-8")) + (1 if output_lines else 0)
        if output_bytes + line_bytes > max_bytes:
            truncated_by = "bytes"
            break
        output_lines.append(line)
        output_bytes += line_bytes

    output_content = "\n".join(output_lines)
    return {
        "content": output_content,
        "truncated": True,
        "truncatedBy": truncated_by,
        "totalLines": total_lines,
        "totalBytes": total_bytes,
        "outputLines": len(output_lines),
        "outputBytes": len(output_content.encode("utf-8")),
        "firstLineExceedsLimit": False,
        "maxLines": max_lines,
        "maxBytes": max_bytes,
    }
