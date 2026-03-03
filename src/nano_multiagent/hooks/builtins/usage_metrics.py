"""Built-in hook that aggregates exact per-session token usage from turn events."""

from __future__ import annotations

from threading import Lock
from typing import Any

from nano_multiagent.hooks.usage_metrics_registry import SessionUsageSnapshot, register_session_usage_reader


def setup(hooks):  # noqa: ANN001, ANN201
    """Register built-in usage aggregation hooks.

    Notes:
        State is intentionally kept in closure variables to support cross-event
        collaboration within one module while still isolating by `session_id`.
    """

    state_lock = Lock()
    totals_by_session: dict[str, SessionUsageSnapshot] = {}
    seen_turn_ids_by_session: dict[str, set[str]] = {}

    def _snapshot_reader(session_id: str) -> SessionUsageSnapshot | None:
        with state_lock:
            totals = totals_by_session.get(session_id)
            if totals is None:
                return None
            return SessionUsageSnapshot(
                prompt_tokens=totals.prompt_tokens,
                completion_tokens=totals.completion_tokens,
                total_tokens=totals.total_tokens,
                last_prompt_tokens=totals.last_prompt_tokens,
                last_completion_tokens=totals.last_completion_tokens,
                last_total_tokens=totals.last_total_tokens,
                turn_count=totals.turn_count,
            )

    register_session_usage_reader(_snapshot_reader)

    def on_turn_end(event, ctx):  # noqa: ANN001
        usage = _extract_usage_metrics(event.get("usage"))
        if usage is None:
            return
        session_id = _resolve_session_id(event=event, fallback_session_id=ctx.session_id)
        if session_id is None:
            return
        turn_id = event.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            turn_id = None

        with state_lock:
            seen_turn_ids = seen_turn_ids_by_session.setdefault(session_id, set())
            if turn_id is not None:
                if turn_id in seen_turn_ids:
                    return
                seen_turn_ids.add(turn_id)

            previous = totals_by_session.get(
                session_id,
                SessionUsageSnapshot(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    last_prompt_tokens=0,
                    last_completion_tokens=0,
                    last_total_tokens=0,
                    turn_count=0,
                ),
            )
            prompt_tokens, completion_tokens, total_tokens = usage
            totals_by_session[session_id] = SessionUsageSnapshot(
                prompt_tokens=previous.prompt_tokens + prompt_tokens,
                completion_tokens=previous.completion_tokens + completion_tokens,
                total_tokens=previous.total_tokens + total_tokens,
                last_prompt_tokens=prompt_tokens,
                last_completion_tokens=completion_tokens,
                last_total_tokens=total_tokens,
                turn_count=previous.turn_count + 1,
            )

    def on_session_shutdown(event, ctx):  # noqa: ANN001
        session_id = _resolve_session_id(event=event, fallback_session_id=ctx.session_id)
        if session_id is None:
            return
        with state_lock:
            totals_by_session.pop(session_id, None)
            seen_turn_ids_by_session.pop(session_id, None)

    hooks.on("turn_end", on_turn_end, priority=100, timeout_ms=500)
    hooks.on("session_shutdown", on_session_shutdown, priority=100, timeout_ms=500)


def _resolve_session_id(*, event: Any, fallback_session_id: Any) -> str | None:
    if isinstance(event, dict):
        event_session_id = event.get("session_id")
        if isinstance(event_session_id, str) and event_session_id.strip():
            return event_session_id.strip()
    if isinstance(fallback_session_id, str) and fallback_session_id.strip():
        return fallback_session_id.strip()
    return None


def _extract_usage_metrics(payload: Any) -> tuple[int, int, int] | None:
    if not isinstance(payload, dict):
        return None
    prompt_tokens = payload.get("prompt_tokens")
    completion_tokens = payload.get("completion_tokens")
    total_tokens = payload.get("total_tokens")
    if not _is_non_negative_int(prompt_tokens):
        return None
    if not _is_non_negative_int(completion_tokens):
        return None
    if _is_non_negative_int(total_tokens):
        resolved_total = int(total_tokens)
    else:
        resolved_total = int(prompt_tokens) + int(completion_tokens)
    return int(prompt_tokens), int(completion_tokens), resolved_total


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
