"""Shared kernel-stream delivery for owner-direct background runs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContextStore,
)


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
) -> tuple[str, dict[str, str] | None]:
    """Deliver one kernel run and return its final assistant text and context.

    The helper owns context seeding and cleanup so heartbeat and cron cannot
    diverge in how background runs are routed into the owner's direct chat.
    """

    _seed_owner_direct_stream_context(
        run_context_store=run_context_store,
        run_id=run_id,
        agent_id=agent_id,
        kernel_session_id=kernel_session_id,
        owner_user_id=owner_user_id,
    )

    final_result_text = ""
    popped_ctx: dict[str, str] | None = None
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
            if event.get("event") == "run_status" and event.get("status") in (
                "completed",
                "failed",
                "cancelled",
                "error",
            ):
                break
    finally:
        popped_ctx = _pop_stream_context(
            run_context_store=run_context_store, run_id=run_id
        )

    return final_result_text, popped_ctx


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
