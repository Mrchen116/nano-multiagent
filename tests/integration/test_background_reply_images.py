"""Real background assistant identities enter prepared delivery; controls do not."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)
from personal_assistant.gateway.runtime_delivery.background import build_bg_reply_sender


@pytest.mark.asyncio
@pytest.mark.parametrize("kernel_message_id", ["kernel-message", None])
async def test_background_assistant_replay_passes_stable_identity_to_prepared_delivery(
    kernel_message_id,
):
    delivered = []
    done = asyncio.Event()
    im = SimpleNamespace(connected=True, send_agent_message=AsyncMock())

    async def prepared(text, context, from_session_id, background_returns):
        delivered.append((text, context, from_session_id, background_returns))
        if len(delivered) == 2:
            done.set()

    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: im,
        assistant_reply_delivery=prepared,
    )
    event = {
        "event": "assistant_message",
        "origin": "background_task",
        "run_id": "run-bg",
        "content": "![chart](/workspace/.nanoassistant/exports/chart.png)",
        "_id": 12,
        "background_returns": [{"task_id": "task"}],
    }
    if kernel_message_id:
        event["message_id"] = kernel_message_id

    class Kernel:
        async def stream(self, session_id, *, after_sequence=0):
            yield event
            yield dict(event)
            await asyncio.Event().wait()

    route = ReplyContext(
        channel_name="web_relay",
        target_chat_id="conversation",
        metadata={"existing": "value"},
    )
    manager = BackgroundSubscriptionManager(kernel=Kernel(), bg_reply_sender=sender)
    await manager.ensure(
        BackgroundSubscriptionRequest(
            session_id="kernel-session",
            after_sequence=0,
            reply_context=route,
            agent_id="agent",
        )
    )
    try:
        await asyncio.wait_for(done.wait(), 1)
        text, context, dedupe, returns = delivered[0]
        assert text == event["content"]
        assert returns == ({"task_id": "task"},)
        assert context.metadata["background_agent_id"] == "agent"
        assert context.metadata["background_run_id"] == "run-bg"
        assert context.metadata["background_session_id"] == "kernel-session"
        expected_key = (
            "run-bg:message:kernel-message" if kernel_message_id else "run-bg:event:12"
        )
        assert context.metadata["background_output_key"] == expected_key
        assert delivered[1][1].metadata["background_output_key"] == expected_key
        assert dedupe == "agent|tool_call:kernel-session:12"
        assert route.metadata == {"existing": "value"}
        im.send_agent_message.assert_not_awaited()
    finally:
        await manager.aclose(asyncio.get_running_loop().time() + 1)


@pytest.mark.asyncio
async def test_control_text_keeps_existing_sender_without_assistant_identity():
    prepared = AsyncMock()
    im = SimpleNamespace(connected=True, send_agent_message=AsyncMock())
    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: im, assistant_reply_delivery=prepared
    )
    await sender(
        "Stopped",
        ReplyContext(channel_name="web_relay", target_chat_id="conversation"),
        "agent|tool_call:session:stop-ack",
    )
    prepared.assert_not_awaited()
    im.send_agent_message.assert_awaited_once_with(
        {
            "text": "Stopped",
            "to": "conversation",
            "from_session_id": "agent|tool_call:session:stop-ack",
        }
    )
