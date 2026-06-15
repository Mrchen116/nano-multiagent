"""Built-in hook that publishes realtime SSE-friendly run events."""

from __future__ import annotations

from typing import Any, Mapping

from agent.platform.tools.presentation import resolve_presenter_for_tool


def _resolve_presenter(ctx, name: str):  # noqa: ANN001
    """Resolve the presenter for a tool call, kernel-scoped (refactor-406 决策 12).

    Presentation travels with the tool object: look the tool up in the assembled
    tool registry (injected into the hook context's metadata by
    ``ToolRegistry.execute``) and read its ``.presenter``. Falls back to the
    default presenter when there is no registry, no such tool, or the tool
    declares no presenter (MCP / runtime-discovered tools) — matching the
    pre-migration default-fallback behaviour.
    """
    registry = None
    metadata = getattr(ctx, "metadata", None)
    if isinstance(metadata, Mapping):
        registry = metadata.get("tool_registry")
    tool = None
    if registry is not None:
        getter = getattr(registry, "get", None)
        if callable(getter):
            tool = getter(name)
    return resolve_presenter_for_tool(tool)


def setup(hooks):  # noqa: ANN001, ANN201
    """Register hook handlers that forward run-scoped realtime events."""

    async def on_message_end(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        msg_role = event.get("role")
        if msg_role != "assistant":
            return
        # Include run_origin as "origin" so downstream subscribers (e.g.
        # BackgroundSessionEventSubscriber) can distinguish BACKGROUND_TASK
        # assistant_message events from regular inbound-triggered run outputs.
        run_origin = (
            ctx.metadata.get("run_origin") if hasattr(ctx, "metadata") else None
        )
        payload = {
            "event": "assistant_message",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "message_id": event.get("message_id"),
            "content": event.get("content") or "",
            "metadata": {},
        }
        if run_origin is not None:
            payload["origin"] = run_origin
        ctx.publish_session_event(event="assistant_message", data=payload)

    async def on_tool_call(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        presenter = _resolve_presenter(ctx, event.get("name", ""))
        presentation = presenter.format_start(event.get("arguments") or {})
        payload = {
            "event": "tool_start",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "call_id": event.get("call_id"),
            "name": event.get("name"),
            "arguments": _as_mapping_or_none(event.get("arguments")),
            "presentation": _presentation_dict(presentation),
        }
        ctx.publish_session_event(event="tool_start", data=payload)

    async def on_tool_result(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        presenter = _resolve_presenter(ctx, event.get("name", ""))
        duration_ms = event.get("duration_ms") or 0
        presentation = presenter.format_end(
            event.get("arguments") or {},
            _FakeResult(output=event.get("output"), error=event.get("error")),
            duration_ms=duration_ms,
        )
        payload = {
            "event": "tool_end",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "call_id": event.get("call_id"),
            "name": event.get("name"),
            "arguments": _as_mapping_or_none(event.get("arguments")),
            "status": "failed" if event.get("error") else "completed",
            "duration_ms": duration_ms,
            "error": event.get("error"),
            # bugfix-410-M2 (#97): carry the badge classification onto the SSE event.
            "reason_code": event.get("reason_code"),
            "presentation": _presentation_dict(presentation),
        }
        ctx.publish_session_event(event="tool_end", data=payload)

    async def on_turn_end(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        payload: dict[str, Any] = {
            "event": "turn_end",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "completed": bool(event.get("completed")),
            "stop_reason": event.get("stop_reason"),
        }
        usage = event.get("usage")
        if isinstance(usage, Mapping):
            payload["usage"] = dict(usage)
        cw = event.get("context_window")
        if isinstance(cw, int) and cw > 0:
            payload["context_window"] = cw
        ctx.publish_session_event(event="turn_end", data=payload)

    hooks.on("tool_call", on_tool_call, priority=1000, timeout_ms=500)
    hooks.on("tool_result", on_tool_result, priority=1000, timeout_ms=500)
    hooks.on("message_end", on_message_end, priority=1000, timeout_ms=500)
    hooks.on("turn_end", on_turn_end, priority=1000, timeout_ms=500)


def _extract_run_id(event: Mapping[str, Any]) -> str | None:
    run_id = event.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return None


def _as_mapping_or_none(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _presentation_dict(presentation: Any) -> dict[str, Any]:
    if presentation is None:
        return {"visible": False, "label": "", "summary": "", "detail": None}
    return {
        "visible": getattr(presentation, "visible", False),
        "label": getattr(presentation, "label", ""),
        "summary": getattr(presentation, "summary", ""),
        "detail": dict(getattr(presentation, "detail", {}))
        if getattr(presentation, "detail", None) is not None
        else None,
    }


class _FakeResult:
    """Minimal stand-in for ToolResult consumed by presenter format_end."""

    def __init__(self, output: Any = None, error: str | None = None) -> None:
        self.output = output
        self.error = error
