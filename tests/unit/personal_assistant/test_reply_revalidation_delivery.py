"""Public Gateway delivery frames retain revalidation without publishing drafts."""

from __future__ import annotations

import asyncio

import pytest

from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from tests.helpers.runtime_delivery import delivery_context_store
from .test_steer_bubble_roll import _FakeManager


class _ReplyProcessAckLossManager(_FakeManager):
    """Model an IM link that only loses reply-process acknowledgements."""

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        if payload.get("kind") == "reply_process":
            raise TimeoutError
        return await super().send_json_await_ack(message_type, payload)


@pytest.mark.asyncio
async def test_reply_process_survives_its_ack_timeout() -> None:
    manager = _ReplyProcessAckLossManager(new_message_id="msg-new")
    contexts = delivery_context_store(
        {
            "run-1": {
                "conversation_id": "group-1",
                "message_id": "msg-old",
                "agent_id": "agent-a",
            }
        }
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=contexts,
    )

    async def emit(event):
        pending = observer({"run_id": "run-1", **event})
        if asyncio.iscoroutine(pending):
            await pending

    await emit(
        {
            "event": "draft_withheld",
            "draft_id": "draft-1",
            "source": "assistant",
            "text": "Original complete draft",
        }
    )
    await emit(
        {
            "event": "injection_consumed",
            "source_messages": [{"message_id": "input-2", "sender": "Alice"}],
        }
    )

    items = [
        payload["item"]
        for _, payload in manager.sent
        if payload.get("kind") == "reply_process"
    ]
    assert [item["kind"] for item in items] == [
        "draft",
        "segment_handoff",
        "revalidation",
    ]


@pytest.mark.asyncio
async def test_draft_handoff_and_silent_revalidation_keep_both_process_blocks() -> None:
    manager = _FakeManager(new_message_id="msg-new")
    contexts = delivery_context_store(
        {
            "run-1": {
                "conversation_id": "group-1",
                "message_id": "msg-old",
                "agent_id": "agent-a",
                "discard_empty_completion": True,
                "visibility_policy": ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS,
            }
        }
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=contexts,
    )

    async def emit(event):
        pending = observer({"run_id": "run-1", **event})
        if asyncio.iscoroutine(pending):
            await pending
        await asyncio.sleep(0)

    await emit(
        {
            "event": "draft_withheld",
            "draft_id": "draft-1",
            "source": "assistant",
            "text": "Original complete draft",
            "context_revision": 0,
        }
    )
    await emit(
        {
            "event": "injection_consumed",
            "pending_ids": ["pending-1"],
            "context_revision": 1,
            "source_messages": [
                {
                    "message_id": "input-2",
                    "sender": "Alice",
                    "timestamp": "2026-09-09T01:00:00Z",
                }
            ],
        }
    )
    await emit(
        {
            "event": "assistant_message",
            "message_id": "kernel-final",
            "content": "NO_REPLY",
        }
    )
    await emit({"event": "turn_end", "completed": True})
    await asyncio.sleep(0)

    frames = [payload for _, payload in manager.sent]
    assert not any(
        p.get("kind") in {"message_delta", "message_discarded"} for p in frames
    )
    items = [
        (p["message_id"], p["item"]) for p in frames if p.get("kind") == "reply_process"
    ]
    assert any(
        mid == "msg-old" and item.get("text") == "Original complete draft"
        for mid, item in items
    )
    assert any(
        mid == "msg-old" and item.get("successor_message_id") == "msg-new"
        for mid, item in items
    )
    assert any(
        mid == "msg-new"
        and item.get("source_messages", [{}])[0].get("message_id") == "input-2"
        for mid, item in items
    )
    assert any(
        p.get("kind") == "message_completed" and p["message_id"] == "msg-new"
        for p in frames
    )
