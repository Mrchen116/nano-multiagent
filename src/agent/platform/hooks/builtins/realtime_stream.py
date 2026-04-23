"""Built-in hook that publishes realtime SSE-friendly run events."""

from __future__ import annotations

from typing import Any, Mapping


def setup(hooks):  # noqa: ANN001, ANN201
    """Register hook handlers that forward run-scoped realtime events."""

    async def on_tool_call(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        payload = {
            "event": "tool_start",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "call_id": event.get("call_id"),
            "name": event.get("name"),
            "arguments": _as_mapping_or_none(event.get("arguments")),
        }
        ctx.publish_session_event(event="tool_start", data=payload)

    async def on_tool_result(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        payload = {
            "event": "tool_end",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "call_id": event.get("call_id"),
            "name": event.get("name"),
            "output": event.get("output"),
            "error": event.get("error"),
        }
        ctx.publish_session_event(event="tool_end", data=payload)

    async def on_message_update(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            return
        delta = event.get("delta")
        if not isinstance(delta, str) or not delta:
            return
        payload = {
            "event": "text_delta",
            "run_id": run_id,
            "turn_id": event.get("turn_id"),
            "message_id": event.get("message_id"),
            "delta": delta,
        }
        ctx.publish_session_event(event="text_delta", data=payload)

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
        ctx.publish_session_event(event="turn_end", data=payload)

    async def on_tool_execution_update(event, ctx):  # noqa: ANN001
        if not isinstance(event, Mapping):
            return
        run_id = _extract_run_id(event)
        if run_id is None:
            run_id = _extract_run_id_from_ctx(ctx)
        if run_id is None:
            return
        name = event.get("name")
        call_id = event.get("call_id") or event.get("tool_call_id")
        turn_id = event.get("turn_id") if event.get("turn_id") is not None else ctx.turn_id
        phase = event.get("phase")
        if not isinstance(phase, str):
            return

        base_payload: dict[str, Any] = {
            "run_id": run_id,
            "turn_id": turn_id,
            "call_id": call_id,
            "name": name,
        }
        if phase == "started":
            payload = {
                **base_payload,
                "event": "tool_exec_started",
                "status": event.get("status"),
                "elapsed_ms": event.get("elapsed_ms"),
            }
            ctx.publish_session_event(event="tool_exec_started", data=payload)
            return
        if phase == "running":
            payload = {
                **base_payload,
                "event": "tool_exec_running",
                "status": event.get("status"),
                "elapsed_ms": event.get("elapsed_ms"),
            }
            ctx.publish_session_event(event="tool_exec_running", data=payload)
            return
        if phase == "chunk":
            payload = {
                **base_payload,
                "event": "tool_exec_chunk",
                "stream": event.get("stream"),
                "chunk": event.get("chunk"),
                "seq": event.get("seq"),
            }
            ctx.publish_session_event(event="tool_exec_chunk", data=payload)
            return
        if phase == "exit":
            payload = {
                **base_payload,
                "event": "tool_exec_exit",
                "status": event.get("status"),
                "duration_ms": event.get("duration_ms"),
                "exit_code": event.get("exit_code"),
            }
            ctx.publish_session_event(event="tool_exec_exit", data=payload)

    hooks.on("tool_call", on_tool_call, priority=1000, timeout_ms=500)
    hooks.on("tool_result", on_tool_result, priority=1000, timeout_ms=500)
    hooks.on("tool_execution_update", on_tool_execution_update, priority=1000, timeout_ms=500)
    hooks.on("message_update", on_message_update, priority=1000, timeout_ms=500)
    hooks.on("turn_end", on_turn_end, priority=1000, timeout_ms=500)


def _extract_run_id(event: Mapping[str, Any]) -> str | None:
    run_id = event.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return None


def _extract_run_id_from_ctx(ctx: Any) -> str | None:
    metadata = getattr(ctx, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    run_id = metadata.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return None


def _as_mapping_or_none(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None
