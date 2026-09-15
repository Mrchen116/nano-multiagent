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


class _TurnStartAckLossManager(_FakeManager):
    """Model IM accepting the first turn_start while its ack is lost."""

    def __init__(self) -> None:
        super().__init__(new_message_id="msg-new")
        self.turn_start_attempts = 0
        self.persisted_process: list[tuple[str, dict[str, object]]] = []

    async def send_json(self, message_type: str, payload: dict[str, object]) -> None:
        await super().send_json(message_type, payload)
        if payload.get("kind") == "reply_process":
            self.persisted_process.append(
                (str(payload["message_id"]), dict(payload["item"]))
            )

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        if payload.get("kind") == "turn_start":
            self.sent.append((message_type, payload))
            self.turn_start_attempts += 1
            transition = payload.get("reply_process_transition")
            if isinstance(transition, dict):
                run_id = str(transition["run_id"])
                predecessor = str(transition["predecessor_message_id"])
                self.persisted_process = [
                    (
                        predecessor,
                        {
                            "item_id": f"handoff:{run_id}:msg-new",
                            "kind": "segment_handoff",
                            "run_id": run_id,
                            "successor_message_id": "msg-new",
                        },
                    ),
                    (
                        "msg-new",
                        {
                            "item_id": f"revalidation:{run_id}:msg-new",
                            "kind": "revalidation",
                            "run_id": run_id,
                            "source_messages": transition["source_messages"],
                            "predecessor_message_id": predecessor,
                            "status": "running",
                        },
                    ),
                ]
            if self.turn_start_attempts == 1:
                raise TimeoutError("turn_start ack lost after IM accepted it")
            return {"payload": {"message_id": "msg-new"}}
        return await super().send_json_await_ack(message_type, payload)


@pytest.mark.asyncio
async def test_reply_process_and_body_survive_accepted_turn_start_ack_loss() -> None:
    manager = _TurnStartAckLossManager()
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
        await asyncio.sleep(0)

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
    await emit(
        {
            "event": "assistant_message",
            "message_id": "kernel-final",
            "content": "Updated answer",
        }
    )
    await emit({"event": "turn_end", "completed": True})

    turn_starts = [
        payload for _, payload in manager.sent if payload.get("kind") == "turn_start"
    ]
    assert len(turn_starts) == 2
    assert turn_starts[0]["idempotency_key"] == turn_starts[1]["idempotency_key"]
    assert [item["kind"] for _, item in manager.persisted_process] == [
        "segment_handoff",
        "revalidation",
    ]
    frames = [payload for _, payload in manager.sent]
    assert any(
        payload.get("kind") == "message_delta"
        and payload.get("message_id") == "msg-new"
        and payload.get("delta_text") == "Updated answer"
        for payload in frames
    )
    assert any(
        payload.get("kind") == "message_completed"
        and payload.get("message_id") == "msg-new"
        for payload in frames
    )


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
    turn_start = next(p for p in frames if p.get("kind") == "turn_start")
    transition = turn_start["reply_process_transition"]
    assert transition["predecessor_message_id"] == "msg-old"
    assert transition["include_handoff"] is True
    assert transition["source_messages"][0]["message_id"] == "input-2"
    assert any(
        p.get("kind") == "message_completed" and p["message_id"] == "msg-new"
        for p in frames
    )
