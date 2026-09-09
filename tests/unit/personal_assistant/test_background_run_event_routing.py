"""Background run Process routing, fallback delivery, and shutdown ownership."""

import asyncio
from types import SimpleNamespace

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.background_session_events import (
    BackgroundSessionEventSubscriber,
)
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)


async def test_run_callback_receives_unmarked_process_events_and_suppresses_duplicate_output():
    received = []
    legacy = []
    done = asyncio.Event()
    events = [
        {
            "event": "run_status",
            "run_id": "r",
            "origin": "background_task",
            "revalidate_output": True,
        },
        {"event": "draft_withheld", "run_id": "r", "text": "draft"},
        {"event": "injection_consumed", "run_id": "r", "pending_ids": ["p"]},
        {
            "event": "assistant_message",
            "run_id": "r",
            "origin": "background_task",
            "content": "answer",
        },
        {
            "event": "assistant_message",
            "run_id": "old",
            "origin": "background_task",
            "content": "legacy",
        },
    ]

    async def stream_session(**kwargs):
        for event in events:
            yield event
        await asyncio.Event().wait()

    async def handle(event):
        received.append(event)
        return event["run_id"] == "r"

    async def send(event):
        legacy.append(event["content"])
        done.set()

    subscriber = BackgroundSessionEventSubscriber(
        kernel_client=SimpleNamespace(stream_session=stream_session),
        session_id="s",
        on_event=send,
        bg_run_output_callback=send,
        background_run_event_callback=handle,
    )
    await subscriber.start()
    await asyncio.wait_for(done.wait(), timeout=1)
    await subscriber.aclose(asyncio.get_running_loop().time() + 1)
    assert received == events
    assert legacy == ["legacy"]


async def test_manager_run_callback_alone_admits_subscription_and_freezes_reply_route():
    received = []
    entered = asyncio.Event()
    release = asyncio.Event()

    class Kernel:
        async def stream(self, session_id, **kwargs):
            yield {"event": "draft_withheld", "run_id": "r", "text": "draft"}
            await asyncio.Event().wait()

    async def handle(reply_context, agent_id, session_id, event):
        received.append((reply_context, agent_id, session_id, event))
        entered.set()
        await release.wait()
        return True

    manager = BackgroundSubscriptionManager(
        kernel=Kernel(), background_run_event_callback=handle
    )
    route = ReplyContext(
        channel_name="web", target_chat_id="group", metadata={"key": "original"}
    )
    outcome = await manager.ensure_after_foreground_terminal(
        BackgroundSubscriptionRequest(
            session_id="s", after_sequence=0, reply_context=route, agent_id="a"
        )
    )
    assert outcome.value == "started"
    route.metadata["key"] = "mutated"
    await asyncio.wait_for(entered.wait(), timeout=1)
    close = asyncio.create_task(manager.aclose(asyncio.get_running_loop().time() + 2))
    await asyncio.sleep(0)
    assert not close.done()
    release.set()
    await close
    assert received[0][0].metadata == {"key": "original"}
    assert received[0][1:3] == ("a", "s")
