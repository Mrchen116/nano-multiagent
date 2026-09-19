"""Keep live tool frames and durable shadow history on their established schema."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.shadow_saga import ExternalShadowSagaStore
from tests.helpers.runtime_delivery import delivery_context_store


class _Manager:
    def __init__(self, connected: bool):
        self.connected = connected
        self.frames = []

    async def send_json(self, _message_type, payload):
        self.frames.append(payload)

    async def send_json_await_ack(self, message_type, payload):
        await self.send_json(message_type, payload)
        return {"payload": {"message_id": "message"}}


@pytest.fixture
def delivery(tmp_path: Path):
    store = ExternalShadowSagaStore(db_path=tmp_path / "shadow.sqlite3")
    message = InboundMessage(
        channel_name="feishu:agent",
        text="run tool",
        external_user_id="user",
        external_chat_id="chat",
        is_group=True,
        agent_id="agent",
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="chat",
                agent_id="agent",
                conversation_type="group",
                trigger_source="external",
            ),
            external_event=ExternalInboundEventIdentity(
                connector_account_id="account",
                provider_event_id="event",
            ),
        ),
    )
    saga = store.prepare(message=message, agent_id="agent", owner_id="owner")
    contexts = delivery_context_store(
        {
            "run": {
                "agent_id": "agent",
                "conversation_id": "conversation",
                "message_id": "message",
                "trigger_source": "external",
                "reply_channel_name": "feishu:agent",
                "reply_target_chat_id": "chat",
                "shadow_saga_id": saga.saga_id,
            }
        }
    )
    contexts.get("run").revalidate_output = True
    return store, contexts


async def _emit(observer, tracker, **event):
    result = observer({"run_id": "run", **event})
    if asyncio.iscoroutine(result):
        await result
    await tracker.drain_run("run")


@pytest.mark.parametrize("classification", [None, " user_deny "])
def test_tool_end_keeps_destination_field_conventions(delivery, classification):
    store, contexts = delivery
    manager = _Manager(True)
    tracker = RuntimeDeliveryTaskTracker()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=contexts,
        shadow_bubble_record=store.record,
        task_tracker=tracker,
    )

    async def run():
        await _emit(observer, tracker, event="tool_start", call_id="call", name="read")
        await _emit(
            observer,
            tracker,
            event="tool_end",
            call_id="call",
            name="read",
            error="denied" if classification else None,
            reason_code=classification,
            approval=classification,
        )
        await _emit(observer, tracker, event="turn_end", completed=True)

    asyncio.run(run())
    live = next(
        f["tool_call"] for f in manager.frames if f["kind"] == "tool_call_completed"
    )
    shadow = store.pending_snapshots()[0].tool_calls[0]
    assert (
        live["status"]
        == shadow["status"]
        == ("failed" if classification else "completed")
    )
    assert live["input"] == shadow["input"] == {}
    assert live["output"] is None and live["duration_ms"] is None
    assert "output" not in shadow and "duration_ms" not in shadow
    if classification:
        assert live["reason"] == live["approval"] == classification.strip()
        assert shadow["reason"] == shadow["approval"] == classification
    else:
        assert live["reason"] is None
        assert (
            "reason" not in shadow
            and "approval" not in shadow
            and "approval" not in live
        )


@pytest.mark.parametrize("connected", [True, False])
def test_revalidation_annotation_follows_actual_live_delivery(delivery, connected):
    store, contexts = delivery
    manager = _Manager(connected)
    tracker = RuntimeDeliveryTaskTracker()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=contexts,
        shadow_bubble_record=store.record,
        task_tracker=tracker,
    )
    detail = {"target": "conversation", "text": "hello"}

    async def run():
        await _emit(
            observer,
            tracker,
            event="tool_start",
            call_id="call",
            name="send_message",
            arguments=detail,
            presentation={"summary": "Send hello", "detail": detail, "emoji": "💬"},
        )
        # The first durable projection is not the live-only pending annotation.
        snapshot = store.require_snapshot(contexts.get("run").shadow_message_id)
        assert snapshot.tool_calls[0]["detail"] == detail
        await _emit(
            observer, tracker, event="run_terminal_reconcile", reason="interrupted"
        )

    asyncio.run(run())
    shadow = store.pending_snapshots()[0].tool_calls[0]
    expected = {**detail, "status": "pending_revalidation"} if connected else detail
    assert shadow["detail"] == expected
    assert shadow["input"] == detail and shadow["emoji"] == "💬"
    assert shadow["status"] == "failed" and shadow["reason"] == "interrupted"
    if connected:
        live = next(
            f["tool_call"] for f in manager.frames if f["kind"] == "tool_call_completed"
        )
        assert live["detail"] == expected and live["input"] == detail
    else:
        assert manager.frames == []
