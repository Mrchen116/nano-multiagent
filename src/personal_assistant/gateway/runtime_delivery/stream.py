"""Shared kernel-stream delivery for owner-direct background runs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agent.sdk import TERMINAL_RUN_STATUSES
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContextStore,
)


@dataclass(frozen=True, slots=True)
class StreamRunOutcome:
    """Canonical terminal result of consuming one kernel run stream.

    Args:
        status: Terminal status from ``TERMINAL_RUN_STATUSES``.
        final_text: Latest non-empty assistant message, including partial output.
        context: Delivery context removed from the shared store after consumption.
        error: Kernel-provided failure detail, when present.
    """

    status: str
    final_text: str
    context: dict[str, str] | None
    error: str | None


async def stream_run_to_completion(
    *,
    run_id: str,
    kernel_session_id: str,
    agent_id: str,
    owner_user_id: str,
    kernel: Any,
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore,
    observer: Callable[..., Any] | None,
    stream_anchor: int = 0,
) -> StreamRunOutcome:
    """Deliver one kernel run and return its canonical terminal outcome.

    The helper owns context seeding and cleanup so heartbeat and cron cannot
    diverge in how background runs are routed into the owner's direct chat.

    Raises:
        RuntimeError: The stream closes without a canonical terminal run status.
    """

    _seed_owner_direct_stream_context(
        run_context_store=run_context_store,
        run_id=run_id,
        agent_id=agent_id,
        kernel_session_id=kernel_session_id,
        owner_user_id=owner_user_id,
    )

    final_result_text = ""
    terminal_event: Mapping[str, Any] | None = None
    popped_ctx: dict[str, str] | None = None
    abnormal_terminal_reconciled = False
    try:
        async for event in kernel.stream(
            kernel_session_id, after_sequence=stream_anchor
        ):
            if event.get("run_id") != run_id:
                continue
            if event.get("event") == "assistant_message":
                content = str(event.get("content") or "").strip()
                if content:
                    final_result_text = content
            if observer is not None:
                observation = observer(event)
                if asyncio.iscoroutine(observation):
                    await observation
            if event.get("event") == "run_terminal_reconcile":
                abnormal_terminal_reconciled = True
            if (
                event.get("event") == "run_status"
                and event.get("status") in TERMINAL_RUN_STATUSES
            ):
                terminal_event = event
                status = str(event["status"])
                if (
                    status != "completed"
                    and observer is not None
                    and not abnormal_terminal_reconciled
                ):
                    reconcile = observer(
                        {
                            "event": "run_terminal_reconcile",
                            "run_id": run_id,
                            "reason": _extract_terminal_error(event, status=status)
                            or status,
                            "finalize_bubble": True,
                            "delivery_status": "failed",
                        }
                    )
                    if asyncio.iscoroutine(reconcile):
                        await reconcile
                break
    finally:
        popped_ctx = _pop_stream_context(
            run_context_store=run_context_store, run_id=run_id
        )

    if terminal_event is None:
        raise RuntimeError("stream ended without terminal run_status")
    status = str(terminal_event["status"])
    return StreamRunOutcome(
        status=status,
        final_text=final_result_text,
        context=popped_ctx,
        error=_extract_terminal_error(terminal_event, status=status),
    )


def _extract_terminal_error(
    terminal_event: Mapping[str, Any], *, status: str
) -> str | None:
    error = terminal_event.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, Mapping):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if status == "failed":
        return f"kernel run ended with status={status}"
    return None


def _seed_owner_direct_stream_context(
    *,
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore,
    run_id: str,
    agent_id: str,
    kernel_session_id: str,
    owner_user_id: str,
) -> None:
    if isinstance(run_context_store, RunDeliveryContextStore):
        run_context_store.seed_owner_direct_run(
            run_id=run_id,
            agent_id=agent_id,
            kernel_session_id=kernel_session_id,
            owner_user_id=owner_user_id,
        )
        return
    run_context_store[run_id] = {
        "conversation_id": "",
        "message_id": "",
        "agent_id": agent_id,
        "to_user_id": owner_user_id,
        "kernel_session_id": kernel_session_id,
    }


def _pop_stream_context(
    *,
    run_context_store: dict[str, dict[str, str]] | RunDeliveryContextStore,
    run_id: str,
) -> dict[str, str] | None:
    if isinstance(run_context_store, RunDeliveryContextStore):
        context = run_context_store.get(run_id)
        popped = context.to_legacy_dict() if context is not None else None
        run_context_store.discard(run_id)
        return popped
    return run_context_store.pop(run_id, None)
