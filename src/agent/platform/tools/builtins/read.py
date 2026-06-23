"""Built-in `read` tool for bounded text and image loading."""

import base64
import re
from pathlib import Path
from typing import Any, Mapping

from agent.core.agent.agents_md import (
    find_outermost_git_root,
    iter_agents_md_chain,
    load_agents_md,
)
from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY
from agent.core.errors import ToolError
from agent.core.tools.base import ToolContext
from agent.core.tools.serialization import json_serialize
from agent.platform.tools.constants import (
    DEFAULT_MAX_KILOBYTES,
    DEFAULT_MAX_LINES,
)
from agent.platform.tools.presentation import (
    ToolPresentationEvent,
    _stringify,
    _truncate,
    _with_path,
    display_path as _display_path,
)

_IMAGE_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Presenter (feat-425 决策 3: presentation travels with the tool — class here)
# ---------------------------------------------------------------------------


class _ReadPresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="Read",
            summary=str(args.get("path", "")),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        # feat-409 readfix/failalign: read 的"人话"首先是读了哪个文件——summary 与
        # detail 都带 path。失败态 summary = 干净主参数(path),与成功态同构,绝不含
        # error 文本(error 只进 detail,展开卡渲染一次;折叠行的失败由 ✕ 图标表达)。
        # args.path 是兜底来源;成功时优先用 output.path(display_path,已转 repo 相对)。
        arg_path = str(args.get("path", ""))
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Read",
                summary=arg_path or "failed",
                detail={"path": arg_path, "error": {"message": str(error)}},
            )
        output = getattr(result, "output", None) or {}
        if isinstance(output, Mapping):
            path = str(output.get("path") or arg_path)
            if output.get("type") == "file_unchanged":
                return ToolPresentationEvent(
                    visible=True,
                    label="Read",
                    summary=_with_path(path, "unchanged"),
                    detail={"path": path, "unchanged": True},
                )
            content_blocks = output.get("content", [])
            if isinstance(content_blocks, list):
                has_image = any(
                    isinstance(block, Mapping) and block.get("type") == "image"
                    for block in content_blocks
                )
                if has_image:
                    return ToolPresentationEvent(
                        visible=True,
                        label="Read",
                        summary=_with_path(path, "image"),
                        detail={"path": path, "image": True},
                    )
            # cr4: total_lines 缺失时不要伪造 0——detail 留 None,前端显 "-"/省略,
            # summary 退化为只显路径(不带 "0 lines" 这类误导性零计数)。
            total_lines = output.get("total_lines")
            offset = output.get("offset", 1)
            limit = args.get("limit")
            # feat-409 protoalign: 折叠 summary 对齐原型中文措辞 `<path> · 86 行`
            # (而非英文 "86 lines")。范围读取仍带 `第 X-Y 行`。
            if limit:
                range_text = f"第 {offset}-{offset + limit - 1} 行"
            elif total_lines is not None:
                range_text = f"{total_lines} 行"
            else:
                range_text = ""
            detail = {
                "path": path,
                "total_lines": total_lines,
                "offset": offset,
                "limit": limit,
                "truncated": bool(output.get("truncated", False)),
            }
            return ToolPresentationEvent(
                visible=True,
                label="Read",
                summary=_with_path(path, range_text),
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Read",
            summary=_with_path(arg_path, _truncate(_stringify(output), 80)),
            detail={"path": arg_path} if arg_path else None,
        )


_READ_PRESENTER = _ReadPresenter()


class ReadTool:
    """Read UTF-8 text with pagination or inline supported image formats."""

    name = "read"
    presenter = _READ_PRESENTER  # 决策 12: presentation travels with the tool object
    is_concurrency_safe = True
    max_result_size_chars = None  # Infinity — read results are never compressed
    description = (
        "Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
        f"Images are sent as attachments. For text files, output is truncated to {DEFAULT_MAX_LINES} "
        f"lines or {DEFAULT_MAX_KILOBYTES}KB (whichever is hit first). Use offset/limit for large "
        "files. When you need the full file, continue with offset until complete. "
        "Results are returned using cat -n format, with line numbers starting at 1."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read (relative or absolute)",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Read file content while enforcing sandbox paths and output limits."""

        raw_path = str(args["path"])
        # bugfix-355: boundary check removed — read is allowed from any path.
        # auto_mode_gate routes non-workspace reads through classifier/ask in
        # non-bypass modes; bypass mode explicitly opts out of all checks.
        file_path = ctx.safety.normalize_path(raw_path, cwd=ctx.cwd)

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
        normalized_offset = offset if offset > 1 else None

        # feat-428 机制 B: compute nested-memory injection blocks up front. When the
        # file is unchanged we normally short-circuit, but if there are pending
        # AGENTS.md blocks to (re)inject — e.g. the dedup set was cleared at a
        # compaction boundary — we must NOT take the file_unchanged fast path, or
        # the re-injection would be skipped. fix r1: compute is pure; dedup keys
        # are committed (_commit_nested_dedup) only after the blocks land in the
        # returned content, so a later read failure never strands an AGENTS.md as
        # "loaded but not injected".
        nested_blocks, nested_keys = _nested_memory_blocks(file_path, ctx)

        if ctx.session_file_state is not None and not nested_blocks:
            try:
                if ctx.session_file_state.check_unchanged(
                    str(file_path.resolve()), normalized_offset, limit
                ):
                    return {
                        "type": "file_unchanged",
                        "file": {"filePath": display_path},
                    }
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

            if ctx.session_file_state is not None:
                try:
                    stat = file_path.stat()
                    ctx.session_file_state.record_read(
                        file_path=str(file_path.resolve()),
                        mtime_ns=stat.st_mtime_ns,
                        size=stat.st_size,
                        offset=normalized_offset,
                        limit=limit,
                    )
                except (OSError, ValueError):
                    pass

            image_content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": text_note,
                },
                {
                    "type": "image",
                    "data": encoded,
                    "mimeType": mime_type,
                },
            ]
            # feat-428 机制 B: image reads trigger nested-memory injection too
            # (blocks computed once above, before the file_unchanged check).
            image_content.extend(nested_blocks)
            # fix r1: commit dedup only now that blocks are in the returned content.
            _commit_nested_dedup(ctx, nested_keys)
            return {
                "path": display_path,
                "offset": 1,
                "next_offset": None,
                "total_lines": 0,
                "truncated": False,
                "content": image_content,
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

        content_blocks: list[dict[str, Any]] = [
            {"type": "text", "text": truncation["content"]}
        ]
        # feat-428 机制 B: append nearest AGENTS.md content (in-workspace) or an
        # outside-project path hint (blocks computed once above, before the
        # file_unchanged check; deduped via session_file_state.loaded_agents_md).
        content_blocks.extend(nested_blocks)
        # fix r1: commit dedup only now that blocks are in the returned content
        # (the file body read above already succeeded — no failure can strand them).
        _commit_nested_dedup(ctx, nested_keys)

        response: dict[str, Any] = {
            "path": display_path,
            "offset": offset,
            "next_offset": None,
            "total_lines": total_lines,
            "truncated": bool(truncation["truncated"]),
            "content": content_blocks,
            "details": {"truncation": truncation},
        }

        if ctx.session_file_state is not None:
            try:
                stat = file_path.stat()
                ctx.session_file_state.record_read(
                    file_path=str(file_path.resolve()),
                    mtime_ns=stat.st_mtime_ns,
                    size=stat.st_size,
                    offset=normalized_offset,
                    limit=limit,
                )
            except (OSError, ValueError):
                pass

        return response

    def serialize_result(
        self, output: Any, error: str | None = None
    ) -> str | list[dict[str, Any]]:
        if error is not None:
            return error

        if isinstance(output, Mapping) and output.get("type") == "file_unchanged":
            file_path = output.get("file", {}).get("filePath", "unknown")
            return (
                "File unchanged since last read. The content from the earlier "
                "Read tool_result in this conversation is still current — "
                "refer to that instead of re-reading."
                f" ({file_path})"
            )

        if isinstance(output, Mapping) and "content" in output:
            content_blocks = output["content"]
            if isinstance(content_blocks, list):
                has_image = any(
                    isinstance(block, Mapping) and block.get("type") == "image"
                    for block in content_blocks
                )
                if has_image:
                    return list(content_blocks)

                # feat-428 fix r1: only the file-body text blocks get cat -n line
                # numbers. Injected nested-memory blocks (marked injected=True) carry
                # <project-instructions*> tags that must reach the model verbatim —
                # line-numbering them would corrupt the injected instructions.
                body_texts = [
                    block.get("text", "")
                    for block in content_blocks
                    if isinstance(block, Mapping)
                    and block.get("type") == "text"
                    and not block.get("injected")
                ]
                injected_texts = [
                    block.get("text", "")
                    for block in content_blocks
                    if isinstance(block, Mapping)
                    and block.get("type") == "text"
                    and block.get("injected")
                ]
                combined = "\n".join(body_texts)

                if not combined and not injected_texts:
                    return "<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>"

                offset = output.get("offset", 1)
                numbered_body = _add_line_numbers(combined, offset) if combined else ""
                parts = [p for p in (numbered_body, *injected_texts) if p]
                return "\n".join(parts)

        return json_serialize(output)


# ---------------------------------------------------------------------------
# feat-428 机制 B: read-triggered nested AGENTS.md injection
# ---------------------------------------------------------------------------


def _nested_memory_enabled(ctx: ToolContext) -> bool:
    """Whether 机制 B is active for this session.

    Reads the per-agent ``agent_features.nested_memory`` override when present,
    else falls back to FEATURE_REGISTRY's ``default_on`` (decision 5). The
    ``requires_tool`` registry field does NOT gate here — read.py is the read
    tool, and the real switch is default_on + the per-agent override.
    """
    default_on = bool(FEATURE_REGISTRY["nested_memory"]["default_on"])
    features = ctx.session_metadata.get("agent_features")
    if isinstance(features, Mapping):
        override = features.get("nested_memory")
        if isinstance(override, bool):
            return override
    return default_on


def _commit_nested_dedup(ctx: ToolContext, keys: list[str]) -> None:
    """Record injected AGENTS.md paths into the session dedup set (fix r1).

    Called only after the injection blocks are placed in the returned content, so
    a read that fails mid-way never marks an AGENTS.md as loaded-but-not-injected.
    """
    state = ctx.session_file_state
    if state is None or not keys:
        return
    state.loaded_agents_md.update(keys)


def _nested_memory_blocks(
    file_path: Path, ctx: ToolContext
) -> tuple[list[dict[str, Any]], list[str]]:
    """Compute AGENTS.md injection blocks for a just-read file (机制 B).

    In-workspace reads return each not-yet-injected AGENTS.md on the directory
    chain (file dir … workspace root) as a ``<project-instructions path=...>``
    block carrying the @import-expanded content. Out-of-workspace reads that fall
    inside a git repo return a single ``<project-instructions-hint>`` block
    listing every AGENTS.md path from the file dir up to the outermost git root
    (no content, to save context). Files outside any git repo yield nothing.

    fix r1: this function is **pure** — it does NOT mutate
    ``loaded_agents_md``. It returns ``(blocks, keys)``; the caller commits the
    keys (records dedup) only after the blocks are actually delivered in the
    returned content. Otherwise a later failure (non-UTF-8 main file → ToolError,
    image read OSError) would leave the AGENTS.md marked loaded but never injected,
    permanently skipping it for the session.

    Dedup is via ``ctx.session_file_state.loaded_agents_md`` (shared with 机制 A's
    preseeded workspace root); each AGENTS.md path is injected/hinted once per
    session until the compaction boundary clears the set.
    """
    if not _nested_memory_enabled(ctx):
        return [], []
    state = ctx.session_file_state
    if state is None:
        return [], []

    # fix r1: resolve the real file first, then take its parent, so symlinked
    # directories walk the real chain and the dedup keys match
    # is_path_in_workspace (which also resolves). iter_agents_md_chain resolves
    # internally too.
    resolved_file = file_path.resolve()
    file_dir = resolved_file.parent
    # ctx.repo_root is the session's workspace_root (rewritten by the registry's
    # _resolve_execution_context), so is_path_in_workspace anchors workspace_root.
    if ctx.safety.is_path_in_workspace(resolved_file):
        return _inside_workspace_blocks(file_dir, ctx.repo_root, state)
    return _outside_workspace_blocks(file_dir, state)


def _inside_workspace_blocks(
    file_dir: Path, workspace_root: Path, state: Any
) -> tuple[list[dict[str, Any]], list[str]]:
    blocks: list[dict[str, Any]] = []
    keys: list[str] = []
    for agents_path in iter_agents_md_chain(file_dir, top=workspace_root):
        key = str(agents_path.resolve())
        if key in state.loaded_agents_md or key in keys:
            continue
        content = load_agents_md(agents_path)
        if content is None:
            continue
        keys.append(key)
        blocks.append(
            {
                "type": "text",
                "injected": True,
                "text": (
                    f'<project-instructions path="{key}">\n'
                    f"{content}\n"
                    "</project-instructions>"
                ),
            }
        )
    return blocks, keys


def _outside_workspace_blocks(
    file_dir: Path, state: Any
) -> tuple[list[dict[str, Any]], list[str]]:
    repo_root = find_outermost_git_root(file_dir)
    if repo_root is None:
        return [], []
    new_paths: list[str] = []
    for agents_path in iter_agents_md_chain(file_dir, top=repo_root):
        key = str(agents_path.resolve())
        if key in state.loaded_agents_md or key in new_paths:
            continue
        new_paths.append(key)
    if not new_paths:
        return [], []
    paths_block = "\n".join(f"  {p}" for p in new_paths)
    hint = (
        "<project-instructions-hint>\n"
        "The file you just read is outside your workspace, in the project rooted "
        f"at {repo_root.resolve()}.\n"
        "This project ships instruction file(s) describing its conventions, not "
        "loaded here to save context:\n"
        f"{paths_block}\n"
        "Read any of them with the read tool if you need this project's "
        "conventions before working in it.\n"
        "</project-instructions-hint>"
    )
    return [{"type": "text", "injected": True, "text": hint}], new_paths


def _add_line_numbers(text: str, start_line: int = 1) -> str:
    if not text:
        return text
    lines = re.split(r"\r?\n", text)
    return "\n".join(
        _format_line_number(index + start_line, line)
        for index, line in enumerate(lines)
    )


def _format_line_number(line_num: int, line: str) -> str:
    num_str = str(line_num)
    if len(num_str) >= 6:
        return f"{num_str}\u2192{line}"
    return f"{num_str:>6}\u2192{line}"


def _image_mime_type(path: Path) -> str | None:
    return _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())


def _image_dimensions(
    image_bytes: bytes, mime_type: str
) -> tuple[int | None, int | None]:
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

        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if segment_length < 7:
                return None, None
            height = int.from_bytes(
                image_bytes[segment_start + 1 : segment_start + 3], "big"
            )
            width = int.from_bytes(
                image_bytes[segment_start + 3 : segment_start + 5], "big"
            )
            return width, height

        index = segment_end
    return None, None


def _webp_dimensions(image_bytes: bytes) -> tuple[int | None, int | None]:
    if (
        len(image_bytes) < 30
        or image_bytes[:4] != b"RIFF"
        or image_bytes[8:12] != b"WEBP"
    ):
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
    if (
        chunk_type == b"VP8 "
        and len(image_bytes) >= 30
        and image_bytes[23:26] == b"\x9d\x01\x2a"
    ):
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


def _truncate_head_lines(
    lines: list[str], *, max_lines: int, max_bytes: int
) -> dict[str, Any]:
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
        "maxLines": max_lines,
        "maxBytes": max_bytes,
    }
