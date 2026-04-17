"""Built-in `read` tool for bounded text and image loading."""

import base64
import math
from pathlib import Path
from typing import Any, Mapping

from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.tools.constants import (
    DEFAULT_MAX_KILOBYTES,
    DEFAULT_MAX_LINES,
)

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
    is_concurrency_safe = True
    description = (
        "Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
        f"Images are sent as attachments. For text files, output is truncated to {DEFAULT_MAX_LINES} "
        f"lines or {DEFAULT_MAX_KILOBYTES}KB (whichever is hit first). Use offset/limit for large "
        "files. When you need the full file, continue with offset until complete."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read (relative or absolute)"},
            "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
            "limit": {"type": "integer", "description": "Maximum number of lines to read"},
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

        offset = int(args.get("offset", 1))
        if offset < 1:
            raise ToolError("offset must be >= 1", tool_name=self.name)

        limit = args.get("limit")
        if limit is not None:
            limit = int(limit)
            if limit < 1:
                raise ToolError("limit must be >= 1", tool_name=self.name)

        display_path = _display_path(file_path, ctx.repo_root)
        cache_key = (file_path, offset, limit)

        if ctx.read_file_state is not None:
            try:
                stat = file_path.stat()
                mtime_ms = math.floor(stat.st_mtime * 1000)
                size = stat.st_size
                cached = ctx.read_file_state.get(cache_key)
                if cached is not None and cached == (mtime_ms, size):
                    return {"type": "file_unchanged", "file": {"filePath": display_path}}
            except (OSError, ValueError):
                pass

        mime_type = _image_mime_type(file_path)
        if mime_type is not None:
            image_bytes = file_path.read_bytes()
            encoded = base64.b64encode(image_bytes).decode("ascii")
            width, height = _image_dimensions(image_bytes, mime_type)
            text_note = f"Read image file [{mime_type}]"
            if width is not None and height is not None:
                text_note = (
                    f"{text_note}\n"
                    f"[Image: original {width}x{height}, displayed at {width}x{height}. "
                    "Multiply coordinates by 1.0 to map to original image.]"
                )

            if ctx.read_file_state is not None:
                try:
                    stat = file_path.stat()
                    mtime_ms = math.floor(stat.st_mtime * 1000)
                    size = stat.st_size
                    ctx.read_file_state.set(cache_key, (mtime_ms, size))
                except (OSError, ValueError):
                    pass

            return {
                "path": display_path,
                "offset": 1,
                "next_offset": None,
                "total_lines": 0,
                "truncated": False,
                "content": [
                    {
                        "type": "text",
                        "text": text_note,
                    },
                    {
                        "type": "image",
                        "data": encoded,
                        "mimeType": mime_type,
                    },
                ],
            }

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
            "path": display_path,
            "offset": offset,
            "next_offset": next_offset,
            "total_lines": total_lines,
            "truncated": bool(truncation["truncated"]),
            "content": [{"type": "text", "text": rendered}],
        }
        if details is not None:
            response["details"] = details

        if ctx.read_file_state is not None:
            try:
                stat = file_path.stat()
                mtime_ms = math.floor(stat.st_mtime * 1000)
                size = stat.st_size
                ctx.read_file_state.set(cache_key, (mtime_ms, size))
            except (OSError, ValueError):
                pass

        return response

    def serialize_result(self, output: Any) -> str:
        if isinstance(output, Mapping) and output.get("type") == "file_unchanged":
            file_path = output.get("file", {}).get("filePath", "unknown")
            return (
                "File unchanged since last read. The content from the earlier "
                "Read tool_result in this conversation is still current — "
                "refer to that instead of re-reading."
                f" ({file_path})"
            )
        return json_serialize(output)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _image_mime_type(path: Path) -> str | None:
    return _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())


def _image_dimensions(image_bytes: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png":
        return _png_dimensions(image_bytes)
    if mime_type == "image/gif":
        return _gif_dimensions(image_bytes)
    if mime_type == "image/jpeg":
        return _jpeg_dimensions(image_bytes)
    if mime_type == "image/webp":
        return _webp_dimensions(image_bytes)
    return None, None


def _png_dimensions(image_bytes: bytes) -> tuple[int | None, int | None]:
    if len(image_bytes) < 24 or image_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    if image_bytes[12:16] != b"IHDR":
        return None, None
    width = int.from_bytes(image_bytes[16:20], "big")
    height = int.from_bytes(image_bytes[20:24], "big")
    return width, height


def _gif_dimensions(image_bytes: bytes) -> tuple[int | None, int | None]:
    if len(image_bytes) < 10 or image_bytes[:6] not in {b"GIF87a", b"GIF89a"}:
        return None, None
    width = int.from_bytes(image_bytes[6:8], "little")
    height = int.from_bytes(image_bytes[8:10], "little")
    return width, height


def _jpeg_dimensions(image_bytes: bytes) -> tuple[int | None, int | None]:
    if len(image_bytes) < 4 or image_bytes[:2] != b"\xff\xd8":
        return None, None

    index = 2
    while index + 1 < len(image_bytes):
        if image_bytes[index] != 0xFF:
            index += 1
            continue
        while index < len(image_bytes) and image_bytes[index] == 0xFF:
            index += 1
        if index >= len(image_bytes):
            return None, None

        marker = image_bytes[index]
        index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 1 >= len(image_bytes):
            return None, None
        segment_length = int.from_bytes(image_bytes[index : index + 2], "big")
        if segment_length < 2:
            return None, None
        segment_start = index + 2
        segment_end = index + segment_length
        if segment_end > len(image_bytes):
            return None, None

        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length < 7:
                return None, None
            height = int.from_bytes(image_bytes[segment_start + 1 : segment_start + 3], "big")
            width = int.from_bytes(image_bytes[segment_start + 3 : segment_start + 5], "big")
            return width, height

        index = segment_end
    return None, None


def _webp_dimensions(image_bytes: bytes) -> tuple[int | None, int | None]:
    if len(image_bytes) < 30 or image_bytes[:4] != b"RIFF" or image_bytes[8:12] != b"WEBP":
        return None, None

    chunk_type = image_bytes[12:16]
    if chunk_type == b"VP8X" and len(image_bytes) >= 30:
        width = int.from_bytes(image_bytes[24:27], "little") + 1
        height = int.from_bytes(image_bytes[27:30], "little") + 1
        return width, height
    if chunk_type == b"VP8L" and len(image_bytes) >= 25 and image_bytes[20] == 0x2F:
        bits = int.from_bytes(image_bytes[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk_type == b"VP8 " and len(image_bytes) >= 30 and image_bytes[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(image_bytes[26:28], "little") & 0x3FFF
        height = int.from_bytes(image_bytes[28:30], "little") & 0x3FFF
        return width, height
    return None, None


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
