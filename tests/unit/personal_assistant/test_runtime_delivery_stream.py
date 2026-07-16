"""Shared background stream delivery preserves canonical terminal outcomes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from personal_assistant.gateway.runtime_delivery.stream import (
    StreamRunOutcome,
    stream_run_to_completion,
)


class _StreamingKernel:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    async def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        del session_id, after_sequence
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_stream_returns_failed_terminal_outcome_with_partial_text() -> None:
    observed: list[dict[str, Any]] = []
    context_store: dict[str, dict[str, str]] = {}
    kernel = _StreamingKernel(
        [
            {"run_id": "run-1", "event": "assistant_message", "content": "partial"},
            # "error" is not a canonical terminal run status and must not stop
            # consumption before the actual failed status arrives.
            {"run_id": "run-1", "event": "run_status", "status": "error"},
            {
                "run_id": "run-1",
                "event": "run_status",
                "status": "failed",
                "error": {"message": "upstream failed"},
            },
        ]
    )

    outcome = await stream_run_to_completion(
        run_id="run-1",
        kernel_session_id="session-1",
        agent_id="agent-a",
        owner_user_id="owner-a",
        kernel=kernel,
        run_context_store=context_store,
        observer=observed.append,
    )

    assert outcome == StreamRunOutcome(
        status="failed",
        final_text="partial",
        context={
            "conversation_id": "",
            "message_id": "",
            "agent_id": "agent-a",
            "to_user_id": "owner-a",
            "kernel_session_id": "session-1",
        },
        error="upstream failed",
    )
    assert [
        event.get("status") for event in observed if event["event"] == "run_status"
    ] == [
        "error",
        "failed",
    ]
    assert context_store == {}


@pytest.mark.asyncio
async def test_stream_returns_cancelled_terminal_outcome() -> None:
    outcome = await stream_run_to_completion(
        run_id="run-cancelled",
        kernel_session_id="session-1",
        agent_id="agent-a",
        owner_user_id="owner-a",
        kernel=_StreamingKernel(
            [
                {
                    "run_id": "run-cancelled",
                    "event": "run_status",
                    "status": "cancelled",
                }
            ]
        ),
        run_context_store={},
        observer=None,
    )

    assert outcome.status == "cancelled"
    assert outcome.final_text == ""
    assert outcome.error is None


@pytest.mark.asyncio
async def test_stream_ending_without_terminal_status_fails_instead_of_hanging() -> None:
    context_store: dict[str, dict[str, str]] = {}

    with pytest.raises(RuntimeError, match="stream ended without terminal run_status"):
        await stream_run_to_completion(
            run_id="run-missing-terminal",
            kernel_session_id="session-1",
            agent_id="agent-a",
            owner_user_id="owner-a",
            kernel=_StreamingKernel(
                [
                    {
                        "run_id": "run-missing-terminal",
                        "event": "assistant_message",
                        "content": "partial",
                    }
                ]
            ),
            run_context_store=context_store,
            observer=None,
        )

    assert context_store == {}
