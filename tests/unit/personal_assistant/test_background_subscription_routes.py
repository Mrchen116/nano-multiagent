"""Per-run notice routing owned by persistent background subscriptions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
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

    def stream(
        self, _session_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        del after_sequence

        async def _generate() -> AsyncIterator[dict[str, Any]]:
            while True:
                event = await self.events.get()
                if event is None:
                    return
                yield event

        return _generate()


def _request() -> BackgroundSubscriptionRequest:
    return BackgroundSubscriptionRequest(
        session_id="sess-bg",
        after_sequence=7,
        reply_context=ReplyContext(
            channel_name="web_relay", target_chat_id="conv-original"
        ),
        agent_id="agent-a",
    )


@pytest.mark.asyncio
async def test_session_event_uses_exact_registered_trace_route() -> None:
    """A live subscriber routes each notice by its originating run trace."""

    kernel = _QueuedKernel()
    delivered: list[tuple[str, str, str, str]] = []
    event_seen = asyncio.Event()

    async def _on_session_event(
        reply_context: ReplyContext,
        agent_id: str,
        kernel_session_id: str,
        event: Mapping[str, Any],
    ) -> None:
        delivered.append(
            (
                reply_context.target_chat_id,
                agent_id,
                kernel_session_id,
                str(event["event"]),
            )
        )
        event_seen.set()

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=_on_session_event,
    )
    await manager.ensure(_request())
    manager.register_session_event_route(
        "trace-current",
        ReplyContext(channel_name="web_relay", target_chat_id="conv-current"),
    )
    manager.seal()
    await kernel.events.put(
        {
            "event": "self_evolution_review",
            "originating_trace_id": "trace-current",
        }
    )
    await asyncio.wait_for(event_seen.wait(), timeout=1)

    assert delivered == [
        ("conv-current", "agent-a", "sess-bg", "self_evolution_review")
    ]
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)


@pytest.mark.asyncio
async def test_session_event_missing_route_fails_closed_and_replay_is_consumed_once() -> (
    None
):
    """Unknown traces never guess a target and a consumed route is not reused."""

    kernel = _QueuedKernel()
    delivered: list[str] = []
    delivered_once = asyncio.Event()

    async def _on_session_event(
        reply_context: ReplyContext,
        _agent_id: str,
        _kernel_session_id: str,
        _event: Mapping[str, Any],
    ) -> None:
        delivered.append(reply_context.target_chat_id)
        delivered_once.set()

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=_on_session_event,
    )
    manager.register_session_event_route(
        "trace-once",
        ReplyContext(channel_name="web_relay", target_chat_id="conv-once"),
    )
    await manager.ensure(_request())
    await kernel.events.put(
        {"event": "self_evolution_review", "originating_trace_id": "trace-missing"}
    )
    event = {
        "event": "self_evolution_review",
        "originating_trace_id": "trace-once",
    }
    await kernel.events.put(event)
    await kernel.events.put(dict(event))
    await asyncio.wait_for(delivered_once.wait(), timeout=1)
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)

    assert delivered == ["conv-once"]


@pytest.mark.asyncio
async def test_session_event_routes_evict_oldest_after_capacity() -> None:
    """Unconsumed run routes stay bounded without evicting newer turns."""

    kernel = _QueuedKernel()
    delivered: list[str] = []
    newest_seen = asyncio.Event()

    async def _on_session_event(
        reply_context: ReplyContext,
        _agent_id: str,
        _kernel_session_id: str,
        _event: Mapping[str, Any],
    ) -> None:
        delivered.append(reply_context.target_chat_id)
        newest_seen.set()

    manager = BackgroundSubscriptionManager(
        kernel=kernel,
        session_event_callback=_on_session_event,
    )
    for index in range(4097):
        manager.register_session_event_route(
            f"trace-{index}",
            ReplyContext(channel_name="web_relay", target_chat_id=f"conv-{index}"),
        )
    await manager.ensure(_request())
    await kernel.events.put(
        {"event": "self_evolution_review", "originating_trace_id": "trace-0"}
    )
    await kernel.events.put(
        {"event": "self_evolution_review", "originating_trace_id": "trace-4096"}
    )
    await asyncio.wait_for(newest_seen.wait(), timeout=1)
    await kernel.events.put(None)
    await manager.aclose(asyncio.get_running_loop().time() + 1)

    assert delivered == ["conv-4096"]
