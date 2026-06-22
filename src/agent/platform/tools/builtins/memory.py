"""Built-in `memory` tool: thin platform wrapper over core/memory MemoryStore.

Responsibilities:
- Expose add / replace / remove actions for MEMORY.md and USER.md to the LLM.
- Resolve the memory_root from ToolContext.session_metadata via ConfigResolver.
- Return structured ``{"success": bool, ...}`` dicts; never raise from run().

Architecture: ``platform`` layer — imports ``core/memory`` and ``core/tools``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from agent.core.memory.store import MemoryEntry, MemorySource, MemoryStore
from agent.core.memory.path import derive_memory_root
from agent.platform.tools.presentation import (
    ToolPresentationEvent,
    _enforce_cap,
    _summarize_memory,
)

# Actions supported by this tool (design §4 interface)
_SUPPORTED_ACTIONS = frozenset({"add", "replace", "remove"})
_VALID_TARGETS = frozenset({"memory", "user"})


# ---------------------------------------------------------------------------
# Presenter (feat-425 决策 3: presentation travels with the tool — class here)
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
        content = str(args.get("content", ""))
        if error:
            # feat-409 failalign: 失败态 summary = 干净主参数(人话 memory 摘要),不含 error。
            return ToolPresentationEvent(
                visible=True,
                label="Memory",
                summary=_summarize_memory(action, target, content) or "failed",
                detail={"error": {"message": str(error)}},
            )
        success = (
            bool(output.get("success", True)) if isinstance(output, Mapping) else True
        )
        message = str(output.get("message", "")) if isinstance(output, Mapping) else ""
        if not success:
            err = str(output.get("error", "")) if isinstance(output, Mapping) else ""
            # feat-409 failalign: success=False 失败态 summary = 干净主参数(人话 memory
            # 摘要),不含 error 文本;error 进 detail.message 供 MemoryCard 渲染一次。
            return ToolPresentationEvent(
                visible=True,
                label="Memory",
                summary=_summarize_memory(action, target, content) or "failed",
                detail={
                    "action": action,
                    "target": target,
                    "content": content,
                    "message": err,
                    "success": False,
                },
            )
        detail = _enforce_cap(
            {
                "action": action,
                "target": target,
                "content": content,
                "message": message,
                "success": True,
            }
        )
        return ToolPresentationEvent(
            visible=True,
            label="Memory",
            # feat-409 protoalign: 折叠 summary 对齐原型 `+project: "内容摘录…"`
            # —— ±action 符号 + target + 内容预览,而非裸 `add project`。
            summary=_summarize_memory(action, target, content) or message,
            detail=detail,
        )


_MEMORY_PRESENTER = _MemoryPresenter()


class MemoryTool:
    """Save durable information to persistent memory across sessions.

    Two targets:
    - ``memory``: Agent's own notes — environment facts, project conventions, lessons.
    - ``user``: User profile — name, role, preferences, communication style.

    The memory_root is resolved at run-time from ``ToolContext.session_metadata``
    using the key ``memory_root`` (injected by product bootstrap). Falls back to
    ``cwd`` when not present — this ensures the tool works in test contexts.

    Args:
        memory_root: Optional fixed memory root. When ``None``, resolved from
            ToolContext.session_metadata["memory_root"] at run time.
    """

    name = "memory"
    is_concurrency_safe = False
    max_result_size_chars = 10_000
    presenter = _MEMORY_PRESENTER  # 决策 12: presentation travels with the tool object

    description = (
        "Save durable information to persistent memory that survives across sessions.\n\n"
        "Memory is injected into future turns — keep entries compact and factual.\n\n"
        "TWO TARGETS:\n"
        "- 'user': who the user is — name, role, preferences, pet peeves.\n"
        "- 'memory': your notes — environment facts, conventions, tool quirks, lessons.\n\n"
        "ACTIONS:\n"
        "- add: Append a new entry.\n"
        "- replace: Update an existing entry (old_text identifies it by substring match).\n"
        "- remove: Delete an existing entry (old_text identifies it).\n\n"
        "WHEN TO SAVE: User corrects you, shares a preference, you discover a stable "
        "environment fact, or you identify a convention worth remembering.\n\n"
        "DO NOT SAVE: Task progress, session outcomes, temporary state, trivial facts "
        "that are easily re-discovered."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove"],
                "description": "The action to perform.",
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which store: 'memory' for personal notes, 'user' for user profile.",
            },
            "content": {
                "type": "string",
                "description": "Entry content for add/replace.",
            },
            "old_text": {
                "type": "string",
                "description": "Unique substring identifying the entry to replace or remove.",
            },
        },
        "required": ["action", "target"],
        "additionalProperties": False,
    }

    def __init__(self, *, memory_root: Path | None = None) -> None:
        self._fixed_memory_root = memory_root

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        """Dispatch the requested action; return structured success/error dict."""
        action = str(args.get("action", ""))
        target = str(args.get("target", ""))

        if action not in _SUPPORTED_ACTIONS:
            return {
                "success": False,
                "error": f"Unknown action '{action}'; supported: {sorted(_SUPPORTED_ACTIONS)}",
            }

        if target not in _VALID_TARGETS:
            return {
                "success": False,
                "error": f"Unknown target '{target}'; expected 'memory' or 'user'",
            }

        memory_root = self._resolve_memory_root(ctx)
        store = MemoryStore(memory_root=memory_root)

        try:
            return self._dispatch(action, target, args, store, ctx)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Unexpected error: {exc}"}

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        """Serialize tool result to a string for the LLM."""
        if error is not None:
            return error
        if isinstance(output, Mapping):
            if not output.get("success", True):
                return f"Error: {output.get('error', 'unknown error')}"
            display = {k: v for k, v in output.items() if k != "success"}
            return json.dumps(display, ensure_ascii=False, indent=2)
        return str(output)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        action: str,
        target: str,
        args: Mapping[str, Any],
        store: MemoryStore,
        ctx: Any,
    ) -> Mapping[str, Any]:
        session_id = self._resolve_session_id(ctx)
        source = MemorySource(session_id=session_id, timestamp=time.time())

        if action == "add":
            return self._add(target, args, store, source)
        if action == "replace":
            return self._replace(target, args, store, source)
        if action == "remove":
            return self._remove(target, args, store)
        raise ValueError(f"Unhandled action '{action}'")  # unreachable

    def _add(
        self,
        target: str,
        args: Mapping[str, Any],
        store: MemoryStore,
        source: MemorySource,
    ) -> Mapping[str, Any]:
        content = args.get("content")
        if not content:
            return {"success": False, "error": "add action requires 'content'"}
        entry = MemoryEntry(text=str(content), source=source)
        store.add(target, entry)  # type: ignore[arg-type]
        return {"success": True, "message": f"added entry to '{target}'"}

    def _replace(
        self,
        target: str,
        args: Mapping[str, Any],
        store: MemoryStore,
        source: MemorySource,
    ) -> Mapping[str, Any]:
        content = args.get("content")
        old_text = args.get("old_text")
        if not content:
            return {"success": False, "error": "replace action requires 'content'"}
        if not old_text:
            return {"success": False, "error": "replace action requires 'old_text'"}
        new_entry = MemoryEntry(text=str(content), source=source)
        store.replace(target, old_text=str(old_text), new_entry=new_entry)  # type: ignore[arg-type]
        return {"success": True, "message": f"replaced entry in '{target}'"}

    def _remove(
        self, target: str, args: Mapping[str, Any], store: MemoryStore
    ) -> Mapping[str, Any]:
        old_text = args.get("old_text")
        if not old_text:
            return {"success": False, "error": "remove action requires 'old_text'"}
        store.remove(target, str(old_text))  # type: ignore[arg-type]
        return {"success": True, "message": f"removed entry from '{target}'"}

    # ------------------------------------------------------------------
    # Context resolution helpers
    # ------------------------------------------------------------------

    def _resolve_memory_root(self, ctx: Any) -> Path:
        """Resolve memory_root per-session from session_metadata.

        Production path: workspace_root + workspace_config_dirname from session_metadata,
        derived via derive_memory_root (shared with runtime _ensure_memory_snapshot so
        MemoryTool writes land in the same directory the runtime reads from).
        Test scaffold: _fixed_memory_root set at construction bypasses metadata lookup.
        """
        if self._fixed_memory_root is not None:
            return self._fixed_memory_root

        metadata = getattr(ctx, "session_metadata", {}) or {}
        workspace_root = metadata.get("workspace_root")
        dirname = metadata.get("workspace_config_dirname")
        if workspace_root and dirname:
            return derive_memory_root(Path(str(workspace_root)), str(dirname))

        # No silent fallback — missing keys indicate misconfigured bootstrap or test context.
        raise RuntimeError(
            "memory_root cannot be resolved: missing workspace_root or "
            "workspace_config_dirname in session_metadata. "
            "Ensure bootstrap injects workspace_config_dirname into default_session_metadata "
            "and runtime injects workspace_root into hook_metadata per-turn."
        )

    def _resolve_session_id(self, ctx: Any) -> str:
        """Extract session_id from context or return a placeholder."""
        session_id = getattr(ctx, "session_id", None)
        if session_id:
            return str(session_id)
        metadata = getattr(ctx, "session_metadata", {}) or {}
        return str(metadata.get("session_id", "<unknown>"))
