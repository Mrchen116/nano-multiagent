"""Tool presentation core: protocol re-export, resolver, default + shared helpers.

Presentation travels with the Tool object (refactor-406 决策 12): each built-in
tool carries its own ``presenter`` instance (the presenter *class* now lives in
that tool's ``builtins/*`` module, feat-425 决策 3), and resolution is
kernel-scoped — ``resolve_presenter_for_tool(tool)`` reads ``tool.presenter`` off
the assembled tool object, falling back to the default presenter when absent (MCP /
``.nano/tools`` runtime-discovered tools, or any tool that declares none).

feat-425 决策 3: the per-tool ``_XxxPresenter`` classes were moved out of this
central file into their own tool modules so that changing a tool's display 只动它
自己的文件,不再回头改这个内核中心文件。What stays here is the shared substrate
every presenter still imports: the protocol/event, the resolver, the default
fallback, and the format helpers (``_enforce_cap`` / ``_truncate`` / ``_stringify``
/ ``_with_path`` / ``_human_size`` / ``_summarize_*`` / ``display_path``). The
legacy module-level global registry was already removed in refactor-406.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

# Re-export so downstream presenter modules and consumers keep importing the
# event/protocol from this central surface (feat-425: ToolPresentationEvent is
# re-exported here; the per-tool presenter classes live in their tool modules).
from agent.core.tools.presentation import (
    ToolPresentationEvent as ToolPresentationEvent,
    ToolPresenter as ToolPresenter,
)

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
            # feat-409 failalign: default presenter 无干净主参数,失败态 summary 用裸
            # "failed"(不拼 error 文本);error 进 detail 供 ErrorCard 渲染一次。
            summary = "failed"
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
DEFAULT_PRESENTER: ToolPresenter = _DEFAULT


# ---------------------------------------------------------------------------
# Shared helpers (imported by the per-tool presenter modules, 决策 3)
# ---------------------------------------------------------------------------


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


def _human_size(byte_count: int) -> str:
    """Human-readable byte size for write summaries (feat-409 protoalign).

    Prototype renders ``新建 1.2KB`` — a compact size, not a raw byte count.
    Sub-1KB stays in bytes (``842B``); KB shows one decimal (``1.2KB``); MB the
    same (``3.4MB``).
    """
    if byte_count < 1024:
        return f"{byte_count}B"
    if byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f}KB"
    return f"{byte_count / (1024 * 1024):.1f}MB"


# feat-409 protoalign: memory action → ± 符号(原型折叠态 `+project: "…"`)。
# add/append/update 记为写入(+);remove/delete 记为删除(-);未知 action 不加符号。
_MEMORY_ACTION_SIGN = {
    "add": "+",
    "append": "+",
    "create": "+",
    "update": "+",
    "set": "+",
    "remove": "-",
    "delete": "-",
}


def _summarize_memory(action: str, target: str, content: str) -> str:
    """Human summary for a memory call: ``±target: "<content preview>"``.

    feat-409 protoalign: 折叠态对齐原型 `+project: "heartbeat 状态文件迁移…"` ——
    动作符号 + target + 内容预览。target 缺失时退化为不带符号的内容预览。
    """
    sign = _MEMORY_ACTION_SIGN.get(action.lower(), "")
    head = f"{sign}{target}" if target else ""
    preview = _truncate(content.replace("\n", " ").strip(), 60)
    if head and preview:
        return f'{head}: "{preview}"'
    if head:
        return head
    if preview:
        return f'"{preview}"'
    return ""


# feat-409 protoalign: skill action → 中文动作(原型折叠态 `创建 skill：log-cleanup`)。
_SKILL_ACTION_VERB = {
    "create": "创建",
    "edit": "编辑",
    "patch": "修补",
    "view": "查看",
    "list": "列出",
    "delete": "删除",
}


def _summarize_skill(action: str, name: str) -> str:
    """Human summary for a skill_manage call: ``<中文动作> skill：<name>``.

    feat-409 protoalign: 折叠态对齐原型 `创建 skill：log-cleanup`。未知 action
    退化为原 action 字面量;name 缺失时只显动作。
    """
    verb = _SKILL_ACTION_VERB.get(action.lower(), action)
    if verb and name:
        return f"{verb} skill：{name}"
    return f"{verb}{name}".strip()


def _with_path(path: str, suffix: str) -> str:
    """Prefix a read summary with its path: ``<path> · <suffix>``.

    feat-409 readfix: read 折叠态文案的"主语"是路径——没有 path 用户看不出读了
    哪个文件。path 为空(理论上不该发生)时降级为只显示 suffix;suffix 为空(如
    total_lines 缺失,cr4)时只显路径,不留孤零零的 " · " 分隔符。
    """
    if not path:
        return suffix
    if not suffix:
        return path
    return f"{path} · {suffix}"


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
