"""Built-in tool presenters for user-facing SSE events (refactor-406 决策 12).

Presentation travels with the Tool object: each built-in tool class carries its
own ``presenter`` instance (attached in ``builtins/*``), and resolution is
kernel-scoped — ``resolve_presenter_for_tool(tool)`` reads ``tool.presenter`` off
the assembled tool object, falling back to the default presenter when absent
(MCP / ``.nano/tools`` runtime-discovered tools, or any tool that declares none).

The legacy module-level global registry (``_PRESENTERS`` / ``register_presenter`` /
``resolve_presenter`` + import-time ``_register_builtin_presenters()``) is removed:
it was a string-keyed, import-side-effect global that the SDK refactor消灭s. The
presenter *classes* below stay (pure functions, no IO); they are instantiated onto
their tool classes instead of registered into a global dict.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any, Mapping

from agent.core.tools.presentation import ToolPresentationEvent, ToolPresenter

PRESENTATION_DETAIL_HARD_CAP_BYTES = 256 * 1024


def resolve_presenter_for_tool(tool: Any) -> ToolPresenter:
    """Return the presenter for an assembled tool object (决策 12, kernel-scoped).

    Reads ``tool.presenter`` (presentation travels with the Tool object). Returns
    the default presenter when the tool is None or declares no presenter — so
    MCP / runtime-discovered tools and any presenter-less tool render with the
    default (visible + truncated args), matching pre-migration behaviour.

    Args:
        tool: The assembled tool object (or None when the name is unknown).

    Returns:
        The tool's ToolPresenter, or the shared default presenter.
    """
    presenter = getattr(tool, "presenter", None) if tool is not None else None
    return presenter or _DEFAULT


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
        # feat-409 readfix: read 的"人话"首先是读了哪个文件——summary 与 detail
        # 都必须带 path,失败态尤其如此(否则只剩 "file does not exist | 0 lines",
        # 用户无从知道读的是哪个文件)。args.path 是兜底来源;成功时优先用 output.path
        # (display_path,已转 repo 相对)。
        arg_path = str(args.get("path", ""))
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Read",
                summary=f"{arg_path}: {_truncate(str(error), 80)}"
                if arg_path
                else f"failed: {_truncate(str(error), 80)}",
                detail={"path": arg_path, "error": {"message": str(error)}},
            )
        output = getattr(result, "output", None) or {}
        if isinstance(output, Mapping):
            path = str(output.get("path") or arg_path)
            if output.get("type") == "file_unchanged":
                file_path = path or str(output.get("file", {}).get("filePath", ""))
                return ToolPresentationEvent(
                    visible=True,
                    label="Read",
                    summary=_with_path(file_path, "unchanged"),
                    detail={"path": file_path, "unchanged": True},
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
            total_lines = output.get("total_lines", 0)
            offset = output.get("offset", 1)
            limit = args.get("limit")
            if limit:
                range_text = f"lines {offset}-{offset + limit - 1}"
            else:
                range_text = f"{total_lines} lines"
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
            # 决策 4:折叠态摘要为人话——优先 args.description(用户写给人看的),
            # 为空时降级为命令首段;不再用 `exit=N elapsed=Xms` 这类裸状态串。
            summary = _summarize_bash(args, command)
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
            # feat-409: body 不再硬截到 500 字——大正文走 _enforce_cap 的 content 字段
            # (统一 256KB 尾截断 + truncated 标记),与其它工具的大字段同一关卡。
            detail = _enforce_cap(
                {
                    "url": url,
                    "final_url": output.get("final_url", url),
                    "status": status,
                    "title": title,
                    "content": str(output.get("content", "")),
                    "truncated": False,
                }
            )
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
# Agent presenter (sub-agent dispatch)
# ---------------------------------------------------------------------------


class _AgentPresenter:
    """Presenter for the `agent` tool (feat-337 task→agent 收尾).

    The agent tool's result schema is ``content`` / ``agent_id`` / ``output_file``
    (not the legacy task ``summary`` / ``artifacts``), keyed by ``status``:
    ``completed`` (content), ``async_launched`` / ``message_queued`` (output_file),
    ``failed`` (error). The full dispatch ``prompt`` (from args) is placed in detail
    **before** the result — it is the key signal a human uses to judge whether the
    dispatch was accurate (spec). The prompt is bounded (a few thousand chars) and
    is intentionally NOT in the ``_enforce_cap`` truncation set.
    """

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Agent",
            summary=_truncate(description, 80),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        description = str(args.get("description", ""))
        prompt = str(args.get("prompt", ""))
        subagent_type = str(args.get("subagent_type") or args.get("category") or "")
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Agent",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        if isinstance(output, Mapping):
            status = str(output.get("status", "completed"))
            # Order matters: description + full prompt first, result fields after —
            # the front-end renders this top-to-bottom (prompt before result, spec).
            detail = _enforce_cap(
                {
                    "description": description,
                    "prompt": prompt,
                    "subagent_type": subagent_type,
                    "status": status,
                    "agent_id": str(output.get("agent_id", "")),
                    "content": str(output.get("content", "")),
                    "output_file": str(output.get("output_file", "")),
                    # fix 3: coerce to plain str (raw may be None / non-JSON-native) so
                    # detail stays JSON-serializable and shape-stable for the front-end.
                    "error": str(output.get("error", "")),
                }
            )
            # The agent tool reports in-band failure via output.status == "failed"
            # (foreground exception path) rather than result.error — surface it as a
            # red "failed" summary like the out-of-band error branch above.
            if status == "failed":
                err = str(output.get("error", ""))
                summary = f"failed: {_truncate(err, 80)}"
            else:
                summary = (
                    _truncate(description, 80) if description else f"status={status}"
                )
            return ToolPresentationEvent(
                visible=True,
                label="Agent",
                summary=summary,
                detail=detail,
            )
        return ToolPresentationEvent(
            visible=True,
            label="Agent",
            summary=_truncate(description, 80),
        )


# ---------------------------------------------------------------------------
# Memory presenter
# ---------------------------------------------------------------------------


class _MemoryPresenter:
    """Presenter for the `memory` tool. Result is ``{success, message|error}``.

    ``action`` / ``target`` / ``content`` live in args (not the result), so detail
    surfaces them from args alongside the result message — the human sees what was
    written, not a truncated JSON blob.
    """

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        action = str(args.get("action", ""))
        target = str(args.get("target", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Memory",
            summary=f"{action} {target}".strip(),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        action = str(args.get("action", ""))
        target = str(args.get("target", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Memory",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        success = (
            bool(output.get("success", True)) if isinstance(output, Mapping) else True
        )
        message = str(output.get("message", "")) if isinstance(output, Mapping) else ""
        if not success:
            err = str(output.get("error", "")) if isinstance(output, Mapping) else ""
            return ToolPresentationEvent(
                visible=True,
                label="Memory",
                summary=f"failed: {_truncate(err, 80)}",
                detail={
                    "action": action,
                    "target": target,
                    "content": str(args.get("content", "")),
                    "message": err,
                    "success": False,
                },
            )
        detail = _enforce_cap(
            {
                "action": action,
                "target": target,
                "content": str(args.get("content", "")),
                "message": message,
                "success": True,
            }
        )
        return ToolPresentationEvent(
            visible=True,
            label="Memory",
            summary=message or f"{action} {target}".strip(),
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Skill manage presenter
# ---------------------------------------------------------------------------


class _SkillManagePresenter:
    """Presenter for the `skill_manage` tool.

    Result varies by action (create/edit/patch → ``{message}``; view → ``{content,
    location}``; list → ``{skills}``). Detail surfaces ``action`` / ``name`` (args)
    plus the result message and best-effort path, so the human sees which skill was
    touched instead of truncated JSON.
    """

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        action = str(args.get("action", ""))
        name = str(args.get("name", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Skill",
            summary=f"{action} {name}".strip(),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        action = str(args.get("action", ""))
        name = str(args.get("name", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Skill",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        success = (
            bool(output.get("success", True)) if isinstance(output, Mapping) else True
        )
        message = str(output.get("message", "")) if isinstance(output, Mapping) else ""
        # view returns content/location; list returns skills — surface what exists.
        path = str(output.get("location", "")) if isinstance(output, Mapping) else ""
        if not success:
            err = str(output.get("error", "")) if isinstance(output, Mapping) else ""
            return ToolPresentationEvent(
                visible=True,
                label="Skill",
                summary=f"failed: {_truncate(err, 80)}",
                detail={
                    "action": action,
                    "name": name,
                    "message": err,
                    "path": path,
                    "success": False,
                },
            )
        detail = _enforce_cap(
            {
                "action": action,
                "name": name,
                "message": message,
                "path": path,
                "content": str(output.get("content", ""))
                if isinstance(output, Mapping)
                else "",
                "success": True,
            }
        )
        return ToolPresentationEvent(
            visible=True,
            label="Skill",
            summary=message or f"{action} {name}".strip(),
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Task stop presenter
# ---------------------------------------------------------------------------


class _TaskStopPresenter:
    """Presenter for the `task_stop` tool. Result is ``{status, task_id, ...}``."""

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        return ToolPresentationEvent(
            visible=True,
            label="TaskStop",
            summary=str(args.get("task_id", "")),
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        task_id = str(args.get("task_id", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="TaskStop",
                summary=f"failed: {_truncate(str(error), 80)}",
                detail={"error": {"message": str(error)}},
            )
        status = (
            str(output.get("status", "killed"))
            if isinstance(output, Mapping)
            else "killed"
        )
        detail = {
            "task_id": str(output.get("task_id", task_id))
            if isinstance(output, Mapping)
            else task_id,
            "status": status,
        }
        if isinstance(output, Mapping):
            if output.get("task_type"):
                detail["task_type"] = str(output["task_type"])
            if output.get("output_file"):
                detail["output_file"] = str(output["output_file"])
        return ToolPresentationEvent(
            visible=True,
            label="TaskStop",
            summary=f"{status} {task_id}".strip(),
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Registration + helpers
# ---------------------------------------------------------------------------


# Built-in presenter singletons (决策 12): each built-in tool class attaches the
# matching instance as its ``presenter`` attribute (presentation travels with the
# tool object). No global registry, no import-time registration side effect.
READ_PRESENTER: ToolPresenter = _ReadPresenter()
WRITE_PRESENTER: ToolPresenter = _WritePresenter()
EDIT_PRESENTER: ToolPresenter = _EditPresenter()
BASH_PRESENTER: ToolPresenter = _BashPresenter()
WEB_FETCH_PRESENTER: ToolPresenter = _WebFetchPresenter()
AGENT_PRESENTER: ToolPresenter = _AgentPresenter()
MEMORY_PRESENTER: ToolPresenter = _MemoryPresenter()
SKILL_MANAGE_PRESENTER: ToolPresenter = _SkillManagePresenter()
TASK_STOP_PRESENTER: ToolPresenter = _TaskStopPresenter()
DEFAULT_PRESENTER: ToolPresenter = _DEFAULT


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


def _summarize_bash(args: Mapping[str, Any], command: str) -> str:
    """Human summary for a bash call: description, or command first-segment fallback.

    决策 4: the collapsed-row text must read as "what this is doing", not a raw
    status code. ``description`` is the field the agent writes for the human; when
    it is empty we fall back to the command's first line (truncated) rather than a
    blank — never to ``exit=… elapsed=…``.
    """
    description = str(args.get("description", "")).strip()
    if description:
        return _truncate(description, 80)
    return _truncate(command.splitlines()[0] if command else command, 80)


def _with_path(path: str, suffix: str) -> str:
    """Prefix a read summary with its path: ``<path> · <suffix>``.

    feat-409 readfix: read 折叠态文案的"主语"是路径——没有 path 用户看不出读了
    哪个文件。path 为空(理论上不该发生)时降级为只显示 suffix。
    """
    return f"{path} · {suffix}" if path else suffix


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
