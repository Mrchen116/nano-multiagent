"""Shared background stream delivery preserves canonical terminal outcomes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from personal_assistant.gateway.inbound_models import ShadowConversationRef
from personal_assistant.gateway.runtime_delivery.stream import (
    StreamRunOutcome,
    stream_run_to_completion,
)
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
    ForegroundTerminalSubscriptionOutcome,
)
from personal_assistant.gateway.runtime_delivery.context import (
    ExternalShadowTarget,
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTerminalProjection,
    RunDeliveryTarget,
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


class _OwnerDirectSkillKernel:
    """Expose one per-run stream plus one persistent session stream."""

    def __init__(self, *, run_id: str, sequence: int) -> None:
        self.run_id = run_id
        self.sequence = sequence
        self.persistent_started = asyncio.Event()
        self.allow_terminal = asyncio.Event()
        self.release_skill = asyncio.Event()
        self.hold_persistent = asyncio.Event()
        self.persistent_calls: list[tuple[str, int]] = []

    async def stream(
        self, session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        task = asyncio.current_task()
        if task is not None and task.get_name().startswith("bg-sse-sub:"):
            self.persistent_calls.append((session_id, after_sequence))
            self.persistent_started.set()
            await self.release_skill.wait()
            yield {
                "event": "skill_created",
                "name": f"skill-{self.run_id}",
                "source": "self_evolution",
                "sequence_num": self.sequence + 1,
            }
            await self.hold_persistent.wait()
            return

        await self.persistent_started.wait()
        await self.allow_terminal.wait()
        yield {
            "event": "run_status",
            "run_id": self.run_id,
            "status": "completed",
        }


@pytest.mark.asyncio
async def test_stream_returns_failed_terminal_outcome_with_partial_text() -> None:
    observed: list[dict[str, Any]] = []
    context_store = RunDeliveryContextStore()
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
        delivery=RunDeliveryTerminalProjection(resolved_conversation_id=None),
        error="upstream failed",
    )
    assert [
        event.get("status") for event in observed if event["event"] == "run_status"
    ] == [
        "error",
        "failed",
    ]
    assert context_store.get("run-1") is None


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
        run_context_store=RunDeliveryContextStore(),
        observer=None,
    )

    assert outcome.status == "cancelled"
    assert outcome.final_text == ""
    assert outcome.error is None


@pytest.mark.asyncio
async def test_stream_ending_without_terminal_status_fails_instead_of_hanging() -> None:
    context_store = RunDeliveryContextStore()

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

    assert context_store.get("run-missing-terminal") is None


@pytest.mark.asyncio
async def test_stream_terminal_projection_preserves_resolved_shadow_conversation() -> (
    None
):
    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-shadow",
            agent_id="agent-a",
            kernel_session_id="session-1",
            delivery_target=RunDeliveryTarget.for_external_shadow(
                ExternalShadowTarget(
                    ref=ShadowConversationRef(
                        conversation_id="conversation-1",
                        im_message_id="message-1",
                    )
                )
            ),
        )
    )

    outcome = await stream_run_to_completion(
        run_id="run-shadow",
        kernel_session_id="session-1",
        agent_id="agent-a",
        owner_user_id="owner-a",
        kernel=_StreamingKernel(
            [
                {
                    "run_id": "run-shadow",
                    "event": "run_status",
                    "status": "completed",
                }
            ]
        ),
        run_context_store=context_store,
        observer=None,
    )

    assert outcome.delivery == RunDeliveryTerminalProjection(
        resolved_conversation_id="conversation-1"
    )
    assert context_store.get("run-shadow") is None


@pytest.mark.asyncio
async def test_stream_terminal_projection_is_absent_after_another_owner_discards_context() -> (
    None
):
    context_store = RunDeliveryContextStore()

    outcome = await stream_run_to_completion(
        run_id="run-discarded",
        kernel_session_id="session-1",
        agent_id="agent-a",
        owner_user_id="owner-a",
        kernel=_StreamingKernel(
            [
                {
                    "run_id": "run-discarded",
                    "event": "run_status",
                    "status": "completed",
                }
            ]
        ),
        run_context_store=context_store,
        observer=lambda _event: context_store.discard("run-discarded"),
    )

    assert outcome.delivery is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_path", "stream_anchor", "skill_before_terminal"),
    [
        ("cron", 0, True),
        ("heartbeat", 17, False),
    ],
)
async def test_owner_direct_stream_admits_one_persistent_skill_owner(
    owner_path: str,
    stream_anchor: int,
    skill_before_terminal: bool,
) -> None:
    """Cron/heartbeat Skills survive before or after their per-run stream ends."""

    run_id = f"run-{owner_path}"
    session_id = f"session-{owner_path}"
    kernel = _OwnerDirectSkillKernel(run_id=run_id, sequence=stream_anchor)
    received: list[tuple[str, str]] = []
    delivered = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle(agent_id: str, event: Mapping[str, object]) -> None:
        received.append((agent_id, str(event["name"])))
        loop.call_soon_threadsafe(delivered.set)

    manager = BackgroundSubscriptionManager(
        kernel=kernel,  # type: ignore[arg-type]
        skill_created_handler=_handle,
    )
    stream_task = asyncio.create_task(
        stream_run_to_completion(
            run_id=run_id,
            kernel_session_id=session_id,
            agent_id="agent-a",
            owner_user_id="owner-a",
            kernel=kernel,
            run_context_store=RunDeliveryContextStore(),
            observer=lambda _event: None,
            stream_anchor=stream_anchor,
            background_subscriptions=manager,
        )
    )
    await asyncio.wait_for(kernel.persistent_started.wait(), timeout=1)

    if skill_before_terminal:
        kernel.release_skill.set()
        await asyncio.wait_for(delivered.wait(), timeout=1)
        assert not stream_task.done()
        kernel.allow_terminal.set()
    else:
        kernel.allow_terminal.set()
        await asyncio.wait_for(stream_task, timeout=1)
        kernel.release_skill.set()
        await asyncio.wait_for(delivered.wait(), timeout=1)

    outcome = await asyncio.wait_for(stream_task, timeout=1)
    dedupe = await manager.ensure_after_foreground_terminal(
        BackgroundSubscriptionRequest(
            session_id=session_id,
            after_sequence=stream_anchor + 10,
            reply_context=None,
            agent_id="agent-a",
        )
    )

    assert outcome.status == "completed"
    assert dedupe is ForegroundTerminalSubscriptionOutcome.ALREADY_ACTIVE
    assert kernel.persistent_calls == [(session_id, stream_anchor)]
    assert received == [("agent-a", f"skill-{run_id}")]
    await manager.aclose(asyncio.get_running_loop().time() + 1)
