"""Public lifecycle tests for Gateway background session subscriptions."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from enum import Enum
from typing import Any

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)


class _QueuedKernel:
    def __init__(self) -> None:
        self.events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.calls: list[tuple[str, int]] = []
        self.started = asyncio.Event()

    async def stream(self, session_id: str, *, after_sequence: int = 0):
        self.calls.append((session_id, after_sequence))
        self.started.set()
        while True:
            event = await self.events.get()
            if event is None:
                return
            yield event


class _YieldGatedKernel(_QueuedKernel):
    """Pause after dequeuing so shutdown races with an already-buffered event."""

    def __init__(self) -> None:
        super().__init__()
        self.dequeued = asyncio.Event()
        self.release_yield = asyncio.Event()

    async def stream(self, session_id: str, *, after_sequence: int = 0):
        self.calls.append((session_id, after_sequence))
        self.started.set()
        event = await self.events.get()
        assert event is not None
        self.dequeued.set()
        await self.release_yield.wait()
        yield event


def _request(session_id: str = "sess-bg") -> BackgroundSubscriptionRequest:
    return BackgroundSubscriptionRequest(
        session_id=session_id,
        after_sequence=7,
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id="conv-original",
        ),
        agent_id="agent-a",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("event_before_subscribe", [True, False])
async def test_marked_skill_routes_by_subscription_agent_before_or_after_terminal(
    event_before_subscribe: bool,
) -> None:
    """Fast replay and slow live review use the same persistent config-sync owner."""
    kernel = _QueuedKernel()
    received: list[tuple[str, str]] = []
    delivered = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle(agent_id: str, event: Mapping[str, object]) -> None:
        received.append((agent_id, str(event["name"])))
        loop.call_soon_threadsafe(delivered.set)

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        skill_created_handler=_handle,
    )
    event = {
        "event": "skill_created",
        "name": "review-skill",
        "source": "self_evolution",
        "sequence_num": 8,
    }
    if event_before_subscribe:
        await kernel.events.put(event)
    outcome = await manager.ensure_after_foreground_terminal(
        BackgroundSubscriptionRequest(
            session_id="sess-bg",
            after_sequence=7,
            reply_context=None,
            agent_id="agent-a",
        )
    )
    if not event_before_subscribe:
        await kernel.events.put(event)

    await asyncio.wait_for(delivered.wait(), timeout=1)

    assert outcome.value == "started"
    assert received == [("agent-a", "review-skill")]
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)


@pytest.mark.asyncio
async def test_existing_subscriber_keeps_single_skill_owner_on_later_turn() -> None:
    """A later foreground terminal reuses the live subscriber without a second owner."""
    kernel = _QueuedKernel()
    received: list[tuple[str, str]] = []
    delivered = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle(agent_id: str, event: Mapping[str, object]) -> None:
        received.append((agent_id, str(event["name"])))
        loop.call_soon_threadsafe(delivered.set)

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        skill_created_handler=_handle,
    )
    request = BackgroundSubscriptionRequest(
        session_id="sess-bg",
        after_sequence=7,
        reply_context=None,
        agent_id="agent-a",
    )
    await manager.ensure(request)
    outcome = await manager.ensure_after_foreground_terminal(
        BackgroundSubscriptionRequest(
            session_id="sess-bg",
            after_sequence=30,
            reply_context=None,
            agent_id="agent-a",
        )
    )
    await kernel.events.put(
        {
            "event": "skill_created",
            "name": "later-review-skill",
            "source": "self_evolution",
            "sequence_num": 31,
        }
    )

    await asyncio.wait_for(delivered.wait(), timeout=1)

    assert outcome.value == "already_active"
    assert kernel.calls == [("sess-bg", 7)]
    assert received == [("agent-a", "later-review-skill")]
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)


@pytest.mark.asyncio
async def test_manager_ensures_once_replays_anchor_and_builds_stable_dedupe_key() -> (
    None
):
    """Repeated ensure keeps one stream and replayed output carries one stable IM key."""

    kernel = _QueuedKernel()
    sent: list[tuple[str, str, str]] = []
    two_sent = asyncio.Event()

    async def _send(text: str, reply_context: ReplyContext, from_session_id: str):
        sent.append((text, reply_context.target_chat_id, from_session_id))
        if len(sent) == 2:
            two_sent.set()

    manager = BackgroundSubscriptionManager(kernel=kernel, bg_reply_sender=_send)
    await manager.ensure(_request())
    await manager.ensure(_request())
    await asyncio.wait_for(kernel.started.wait(), timeout=1)
    event = {
        "event": "assistant_message",
        "origin": "background_task",
        "content": "background result",
        "_id": 42,
    }
    await kernel.events.put(event)
    await kernel.events.put(dict(event))
    await asyncio.wait_for(two_sent.wait(), timeout=1)

    assert kernel.calls == [("sess-bg", 7)]
    assert [target for _, target, _ in sent] == ["conv-original", "conv-original"]
    assert sent[0][2] == sent[1][2] == "agent-a|tool_call:sess-bg:42"

    manager.seal()
    with pytest.raises(RuntimeError, match="sealed"):
        await manager.ensure(_request("sess-late"))
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)


@pytest.mark.asyncio
async def test_manager_seal_does_not_cancel_current_callback_before_close() -> None:
    """Seal only rejects admission; Kernel-era callbacks remain alive until close drains."""

    kernel = _QueuedKernel()
    callback_started = asyncio.Event()
    release_callback = asyncio.Event()

    async def _on_session_event(
        _reply_context: ReplyContext,
        _agent_id: str,
        _kernel_session_id: str,
        _event: Mapping[str, Any],
    ) -> None:
        callback_started.set()
        await release_callback.wait()

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=_on_session_event,
    )
    manager.register_session_event_route(
        "trace-callback-close",
        ReplyContext(channel_name="web_relay", target_chat_id="conv-original"),
    )
    await manager.ensure(_request())
    await kernel.events.put(
        {
            "event": "self_evolution_review",
            "originating_trace_id": "trace-callback-close",
        }
    )
    await asyncio.wait_for(callback_started.wait(), timeout=1)

    manager.seal()
    close_task = asyncio.create_task(
        manager.aclose(asyncio.get_running_loop().time() + 1)
    )
    await asyncio.sleep(0)
    assert not close_task.done()

    release_callback.set()
    await kernel.events.put(None)
    await close_task
    assert not any(
        task.get_name().startswith("bg-sse-sub:")
        for task in asyncio.all_tasks()
        if not task.done()
    )


@pytest.mark.asyncio
async def test_sealed_manager_allows_terminal_ensure_for_existing_session() -> None:
    """Terminal cleanup may idempotently ensure a subscriber admitted before seal."""

    kernel = _QueuedKernel()
    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=lambda _context, _agent, _session, _event: asyncio.sleep(
            0
        ),
    )
    request = _request()
    await manager.ensure(request)
    await asyncio.wait_for(kernel.started.wait(), timeout=1)

    manager.seal()
    await manager.ensure(request)

    assert kernel.calls == [("sess-bg", 7)]
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)


@pytest.mark.asyncio
async def test_terminal_ensure_returns_typed_skip_when_shutdown_rejects_new_session() -> (
    None
):
    """Foreground terminal cleanup observes seal as a typed non-error outcome."""

    manager = BackgroundSubscriptionManager(
        kernel=_QueuedKernel(),
        session_event_callback=lambda _context, _agent, _session, _event: asyncio.sleep(
            0
        ),
    )
    manager.seal()

    outcome = await manager.ensure_after_foreground_terminal(_request())

    assert isinstance(outcome, Enum)
    assert outcome.value == "shutdown_skipped"
    with pytest.raises(RuntimeError, match="sealed"):
        await manager.ensure(_request())


@pytest.mark.asyncio
async def test_close_consumes_event_dequeued_before_stop_request() -> None:
    """A buffered terminal event remains deliverable after close requests stop."""

    kernel = _YieldGatedKernel()
    delivered: list[str] = []

    async def _on_event(
        _reply_context: ReplyContext,
        _agent_id: str,
        _kernel_session_id: str,
        event: Mapping[str, Any],
    ) -> None:
        delivered.append(str(event["event"]))

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=_on_event,
    )
    manager.register_session_event_route(
        "trace-buffered-close",
        ReplyContext(channel_name="web_relay", target_chat_id="conv-original"),
    )
    await manager.ensure(_request())
    await kernel.events.put(
        {
            "event": "self_evolution_review",
            "originating_trace_id": "trace-buffered-close",
        }
    )
    await asyncio.wait_for(kernel.dequeued.wait(), timeout=1)

    close = asyncio.create_task(manager.aclose(asyncio.get_running_loop().time() + 1))
    await asyncio.sleep(0)
    kernel.release_yield.set()
    await close

    assert delivered == ["self_evolution_review"]


@pytest.mark.asyncio
async def test_close_cancels_idle_stream_without_deadline_warning() -> None:
    """An idle subscription has no accepted callback and should close promptly."""

    kernel = _QueuedKernel()
    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=lambda _context, _agent, _session, _event: asyncio.sleep(
            0
        ),
    )
    await manager.ensure(_request())
    await asyncio.wait_for(kernel.started.wait(), timeout=1)

    await manager.aclose(asyncio.get_running_loop().time() + 0.2)

    assert not any(
        task.get_name().startswith("bg-sse-sub:")
        for task in asyncio.all_tasks()
        if not task.done()
    )
