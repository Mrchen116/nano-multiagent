"""Built-in tool presenters and registration for user-facing SSE events."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any, Mapping

from agent.core.tools.presentation import ToolPresentationEvent, ToolPresenter

PRESENTATION_DETAIL_HARD_CAP_BYTES = 256 * 1024


_PRESENTERS: dict[str, ToolPresenter] = {}


def register_presenter(tool_name: str, presenter: ToolPresenter) -> None:
    _PRESENTERS[tool_name] = presenter


def resolve_presenter(tool_name: str) -> ToolPresenter:
    return _PRESENTERS.get(tool_name) or _DEFAULT


class _DefaultPresenter:
    """Fallback for unknown / MCP tools: visible=true, label=name, summary=truncated args."""

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="Tool",
            summary=_truncate(json.dumps(dict(args)), 80),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        detail: dict[str, Any] | None = None
        summary = ""
        if hasattr(result, "error") and result.error:
            summary = f"failed: {_truncate(str(result.error), 80)}"
            detail = {"error": {"message": str(result.error)}}
        else:
            output = getattr(result, "output", None)
            summary = _truncate(_stringify(output), 80)
        return ToolPresentationEvent(
            visible=True,
            label="Tool",
            summary=summary,
            detail=_enforce_cap(detail) if detail else None,
        )


_DEFAULT: ToolPresenter = _DefaultPresenter()


# ---------------------------------------------------------------------------
# Read presenter
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
        output = getattr(result, "output", None) or {}
        if isinstance(output, Mapping):
            if output.get("type") == "file_unchanged":
                return ToolPresentationEvent(
                    visible=True,
                    label="Read",
                    summary="unchanged",
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
                        summary="image",
                    )
            total_lines = output.get("total_lines", 0)
            offset = output.get("offset", 1)
            limit = args.get("limit")
            if limit:
                summary = f"lines {offset}-{offset + limit - 1}"
            else:
                summary = f"{total_lines} lines"
            return ToolPresentationEvent(
                visible=True,
                label="Read",
                summary=summary,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Read",
            summary=_truncate(_stringify(output), 80),
        )


# ---------------------------------------------------------------------------
# Write presenter
# ---------------------------------------------------------------------------


class _WritePresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="Write",
            summary=str(args.get("path", "")),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        output = getattr(result, "output", None) or {}
        path = str(args.get("path", ""))
        if isinstance(output, Mapping):
            write_type = output.get("type")
            content = str(args.get("content", ""))
            byte_count = len(content.encode("utf-8"))
            if write_type == "create":
                summary = f"created ({byte_count} bytes)"
            elif write_type == "update":
                summary = f"overwritten ({byte_count} bytes)"
            else:
                summary = path
            detail = _enforce_cap(
                {
                    "path": path,
                    "content": content,
                    "bytes": byte_count,
                    "truncated": False,
                }
            )
            return ToolPresentationEvent(
                visible=True,
                label="Write",
                summary=summary,
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Write",
            summary=path,
        )


# ---------------------------------------------------------------------------
# Edit presenter
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
            return ToolPresentationEvent(
                visible=True,
                label="Edit",
                summary=f"failed: {_truncate(str(error), 80)}",
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


# ---------------------------------------------------------------------------
# Bash presenter
# ---------------------------------------------------------------------------


class _BashPresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="Bash",
            summary=_truncate(str(args.get("command", "")), 80),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        command = str(args.get("command", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Bash",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        if isinstance(output, Mapping):
            exit_code = output.get("exitCode", 0)
            stdout = output.get("stdout", "")
            stderr = output.get("stderr", "")
            summary = f"exit={exit_code} elapsed={duration_ms}ms"
            detail = _enforce_cap(
                {
                    "command": command,
                    "exit_code": exit_code,
                    "duration_ms": duration_ms,
                    "stdout": stdout or "",
                    "stderr": stderr or "",
                    "truncated": False,
                }
            )
            return ToolPresentationEvent(
                visible=True,
                label="Bash",
                summary=summary,
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Bash",
            summary=f"elapsed={duration_ms}ms",
        )


# ---------------------------------------------------------------------------
# Web fetch presenter
# ---------------------------------------------------------------------------


class _WebFetchPresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="Web",
            summary=_truncate(str(args.get("url", "")), 100),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        url = str(args.get("url", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Web",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        if isinstance(output, Mapping):
            status = output.get("status")
            title = output.get("title", "")
            summary = f"status={status}" + (f" ({title})" if title else "")
            detail = {
                "url": url,
                "final_url": output.get("final_url", url),
                "status": status,
                "title": title,
                "body_excerpt": _truncate(output.get("content", ""), 500),
            }
            return ToolPresentationEvent(
                visible=True,
                label="Web",
                summary=summary,
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Web",
            summary=url,
        )


# ---------------------------------------------------------------------------
# Task presenter
# ---------------------------------------------------------------------------


class _TaskPresenter:
    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Task",
            summary=_truncate(description, 80),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Task",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        if isinstance(output, Mapping):
            status = output.get("status", "completed")
            summary = f"status={status}"
            detail = {
                "description": description,
                "status": status,
                "summary": output.get("summary", ""),
                "artifacts": output.get("artifacts", []),
            }
            return ToolPresentationEvent(
                visible=True,
                label="Task",
                summary=summary,
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Task",
            summary=description,
        )


# ---------------------------------------------------------------------------
# Registration + helpers
# ---------------------------------------------------------------------------


def _register_builtin_presenters() -> None:
    register_presenter("read", _ReadPresenter())
    register_presenter("write", _WritePresenter())
    register_presenter("edit", _EditPresenter())
    register_presenter("bash", _BashPresenter())
    register_presenter("web_fetch", _WebFetchPresenter())
    register_presenter("task", _TaskPresenter())


_register_builtin_presenters()


def _enforce_cap(detail: dict[str, Any]) -> dict[str, Any]:
    """Tail-truncate known large string fields to PRESENTATION_DETAIL_HARD_CAP_BYTES."""
    if not detail:
        return detail
    capped = dict(detail)
    truncated = False
    for field in ("stdout", "stderr", "diff", "content"):
        value = capped.get(field)
        if not isinstance(value, str):
            continue
        encoded = value.encode("utf-8")
        if len(encoded) <= PRESENTATION_DETAIL_HARD_CAP_BYTES:
            continue
        # tail-truncate: keep last N bytes, align to valid UTF-8 boundary
        keep = encoded[-PRESENTATION_DETAIL_HARD_CAP_BYTES:]
        while keep and (keep[0] & 0xC0) == 0x80:
            keep = keep[1:]
        capped[field] = "...[truncated]..." + keep.decode("utf-8", errors="replace")
        truncated = True
    if truncated:
        capped["truncated"] = True
    return capped


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)


def display_path(path: Path, repo_root: Path) -> str:
    """Return a repo-relative display path, falling back to the absolute path.

    Three builtins (write, edit, read) each carried a private copy — consolidated
    here as refactor-395-M1.

    Args:
        path: The absolute file path to display.
        repo_root: The repository root used as the relative-path anchor.

    Returns:
        The relative path string if path is inside repo_root; otherwise the
        absolute path string.
    """
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
