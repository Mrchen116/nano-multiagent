"""External-channel user-visible delivery boundaries for feat-447 M14."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.runtime_delivery.background import (
    build_bg_reply_sender,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from tests.helpers.runtime_delivery import delivery_context_store


class _FakeIMManager:
    connected = True

    def __init__(self) -> None:
        self.agent_messages: list[dict[str, Any]] = []
        self.json_messages: list[tuple[str, dict[str, Any]]] = []

    async def send_agent_message(self, payload: dict[str, Any]) -> None:
        self.agent_messages.append(dict(payload))

    async def send_json(self, message_type: str, payload: dict[str, Any]) -> None:
        self.json_messages.append((message_type, dict(payload)))

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.json_messages.append((message_type, dict(payload)))
        return {"message_type": message_type, "message_id": "notice-1"}


def test_feishu_visible_control_text_goes_to_external_and_shadow_im() -> None:
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []

    def _external_sender(text: str, metadata: dict[str, str]) -> None:
        external.append((text, dict(metadata)))

    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=_external_sender,
    )
    reply_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:app:dm:ou_user",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:app:dm:ou_user",
            "trigger_source": "feishu",
            "shadow_conversation_id": "conv-shadow",
            "feishu_message_id": "om_123",
        },
    )

    asyncio.run(
        sender(
            "已停止当前操作。",
            reply_context,
            "agent-a|tool_call:sess-1:stop-ack",
        )
    )

    assert external == [
        (
            "已停止当前操作。",
            {
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:app:dm:ou_user",
                "reply_phase": "control",
                "reply_dedupe_key": "agent-a|tool_call:sess-1:stop-ack",
                "feishu_message_id": "om_123",
            },
        )
    ]
    assert manager.agent_messages == [
        {
            "text": "已停止当前操作。",
            "to": "conv-shadow",
            "from_session_id": "agent-a|tool_call:sess-1:stop-ack",
        }
    ]


def test_background_external_sync_sender_does_not_block_gateway_event_loop() -> None:
    """A synchronous channel retry cannot hold the subscriber's asyncio loop."""

    manager = _FakeIMManager()
    sender_started = threading.Event()
    release_sender = threading.Event()
    sender_thread_ids: list[int] = []
    loop_thread_id: list[int] = []

    def blocking_external_sender(_text: str, _metadata: dict[str, str]) -> None:
        sender_thread_ids.append(threading.get_ident())
        sender_started.set()
        assert release_sender.wait(1)

    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=blocking_external_sender,
    )
    reply_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:app:dm:ou_user",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:app:dm:ou_user",
            "trigger_source": "feishu",
            "shadow_conversation_id": "conv-shadow",
        },
    )

    async def exercise() -> None:
        loop_thread_id.append(threading.get_ident())
        task = asyncio.create_task(sender("后台结果", reply_context, "background:1"))
        assert await asyncio.to_thread(sender_started.wait, 1)
        await asyncio.sleep(0)
        assert not task.done()
        release_sender.set()
        await task

    asyncio.run(exercise())

    assert sender_thread_ids and sender_thread_ids[0] != loop_thread_id[0]
    assert manager.agent_messages == [
        {
            "text": "后台结果",
            "to": "conv-shadow",
            "from_session_id": "background:1",
        }
    ]


def test_background_external_awaitable_sender_returns_to_gateway_event_loop() -> None:
    """Awaitable channel senders retain their original async execution model."""

    manager = _FakeIMManager()
    loop_thread_id: list[int] = []
    sender_loop_thread_id: list[int] = []

    async def async_external_sender(_text: str, _metadata: dict[str, str]) -> None:
        sender_loop_thread_id.append(threading.get_ident())
        await asyncio.sleep(0)

    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=async_external_sender,
    )
    reply_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:app:dm:ou_user",
        metadata={"external_source": "feishu", "trigger_source": "feishu"},
    )

    async def exercise() -> None:
        loop_thread_id.append(threading.get_ident())
        await sender("后台结果", reply_context, "background:2")

    asyncio.run(exercise())

    assert sender_loop_thread_id == loop_thread_id
    assert manager.agent_messages == []


def test_background_external_failure_does_not_prevent_shadow_delivery() -> None:
    """An external channel failure remains best-effort for the IM mirror."""

    manager = _FakeIMManager()

    def failing_external_sender(_text: str, _metadata: dict[str, str]) -> None:
        raise RuntimeError("simulated provider failure")

    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=failing_external_sender,
    )
    reply_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:app:dm:ou_user",
        metadata={
            "external_source": "feishu",
            "trigger_source": "feishu",
            "shadow_conversation_id": "conv-shadow",
        },
    )

    asyncio.run(sender("后台结果", reply_context, "background:3"))

    assert manager.agent_messages == [
        {
            "text": "后台结果",
            "to": "conv-shadow",
            "from_session_id": "background:3",
        }
    ]


def test_feishu_visible_control_text_goes_to_external_without_im_manager() -> None:
    external: list[tuple[str, dict[str, str]]] = []
    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: None,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
    )
    reply_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:app:dm:ou_user",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:app:dm:ou_user",
            "trigger_source": "feishu",
            "feishu_message_id": "om_123",
        },
    )

    asyncio.run(
        sender(
            "已停止当前操作。",
            reply_context,
            "agent-a|tool_call:sess-1:stop-ack",
        )
    )

    assert external == [
        (
            "已停止当前操作。",
            {
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:app:dm:ou_user",
                "reply_phase": "control",
                "reply_dedupe_key": "agent-a|tool_call:sess-1:stop-ack",
                "feishu_message_id": "om_123",
            },
        )
    ]


def test_feishu_intermediate_reply_goes_to_external_without_im_manager() -> None:
    external: list[tuple[str, dict[str, str]]] = []
    tracker = RuntimeDeliveryTaskTracker()
    run_context_store = delivery_context_store(
        {
            "run-1": {
                "agent_id": "agent-a",
                "trigger_source": "feishu",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "feishu:app:dm:ou_user",
                "reply_thread_id": "om_trigger",
            }
        }
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store=run_context_store,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
        task_tracker=tracker,
    )

    async def exercise() -> None:
        observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kmsg-1",
                "content": "好的，我查一下。",
            }
        )
        observer(
            {
                "event": "tool_start",
                "run_id": "run-1",
                "call_id": "call-1",
                "name": "read",
                "arguments": {},
            }
        )
        observer(
            {
                "event": "turn_end",
                "run_id": "run-1",
                "completed": True,
            }
        )
        await tracker.drain_run("run-1")

    asyncio.run(exercise())

    assert external == [
        (
            "好的，我查一下。",
            {
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:app:dm:ou_user",
                "reply_thread_id": "om_trigger",
                "reply_phase": "intermediate",
                "reply_dedupe_key": "run-1:bubble:kmsg-1",
            },
        )
    ]


@pytest.mark.parametrize("phase", ("intermediate", "final"))
def test_observer_external_sync_reply_does_not_block_gateway_event_loop(
    phase: str,
) -> None:
    """Intermediate and final replies leave the Gateway loop free during retries."""

    sender_started = threading.Event()
    sender_finished = threading.Event()
    release_sender = threading.Event()
    external: list[tuple[str, dict[str, str]]] = []
    tracker = RuntimeDeliveryTaskTracker()
    manager = _FakeIMManager() if phase == "final" else None
    text = f"{phase} reply"

    def blocking_external_sender(reply: str, metadata: dict[str, str]) -> None:
        external.append((reply, dict(metadata)))
        sender_started.set()
        release_sender.wait(0.5)
        sender_finished.set()

    run_context_store = delivery_context_store(
        {
            "run-1": {
                "agent_id": "agent-a",
                "trigger_source": "feishu",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "feishu:app:dm:ou_user",
                "kernel_message_id": "kmsg-1",
                "message_id": "bubble-1",
                "external_current_text": text,
            }
        }
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_context_store,
        external_reply_sender=blocking_external_sender,
        task_tracker=tracker,
    )

    async def exercise() -> None:
        if phase == "intermediate":
            observer(
                {
                    "event": "tool_start",
                    "run_id": "run-1",
                    "call_id": "call-1",
                    "name": "read",
                    "arguments": {},
                }
            )
        else:
            observer({"event": "turn_end", "run_id": "run-1", "completed": True})

        assert await asyncio.to_thread(sender_started.wait, 1)
        loop_tick = asyncio.Event()
        asyncio.get_running_loop().call_soon(loop_tick.set)
        await asyncio.wait_for(loop_tick.wait(), timeout=0.1)
        assert not sender_finished.is_set()
        if manager is not None:
            assert any(
                payload.get("kind") == "message_completed"
                for _message_type, payload in manager.json_messages
            )
        release_sender.set()
        await tracker.drain_run("run-1")

    asyncio.run(exercise())

    assert external == [
        (
            text,
            {
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:app:dm:ou_user",
                "reply_phase": phase,
                "reply_dedupe_key": "run-1:bubble:kmsg-1",
            },
        )
    ]


def test_observer_external_awaitable_sender_returns_to_gateway_event_loop() -> None:
    """Observer delivery preserves asynchronous channel sender compatibility."""

    tracker = RuntimeDeliveryTaskTracker()
    loop_thread_ids: list[int] = []
    sender_thread_ids: list[int] = []

    async def async_external_sender(_text: str, _metadata: dict[str, str]) -> None:
        sender_thread_ids.append(threading.get_ident())
        await asyncio.sleep(0)

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "agent_id": "agent-a",
                    "trigger_source": "feishu",
                    "reply_channel_name": "feishu:agent-a",
                    "reply_target_chat_id": "feishu:app:dm:ou_user",
                    "kernel_message_id": "kmsg-1",
                    "external_current_text": "partial reply",
                }
            }
        ),
        external_reply_sender=async_external_sender,
        task_tracker=tracker,
    )

    async def exercise() -> None:
        loop_thread_ids.append(threading.get_ident())
        observer(
            {
                "event": "tool_start",
                "run_id": "run-1",
                "call_id": "call-1",
                "name": "read",
                "arguments": {},
            }
        )
        await tracker.drain_run("run-1")

    asyncio.run(exercise())

    assert sender_thread_ids == loop_thread_ids


def test_observer_external_failure_does_not_prevent_final_im_delivery() -> None:
    """A normal-reply external failure remains best-effort for the IM final frame."""

    manager = _FakeIMManager()
    tracker = RuntimeDeliveryTaskTracker()

    def failing_external_sender(_text: str, _metadata: dict[str, str]) -> None:
        raise RuntimeError("simulated provider failure")

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "agent_id": "agent-a",
                    "trigger_source": "feishu",
                    "reply_channel_name": "feishu:agent-a",
                    "reply_target_chat_id": "feishu:app:dm:ou_user",
                    "kernel_message_id": "kmsg-1",
                    "message_id": "bubble-1",
                    "external_current_text": "final reply",
                }
            }
        ),
        external_reply_sender=failing_external_sender,
        task_tracker=tracker,
    )

    async def exercise() -> None:
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await tracker.drain_run("run-1")

    asyncio.run(exercise())

    assert any(
        payload.get("kind") == "message_completed"
        for _message_type, payload in manager.json_messages
    )


def test_external_output_is_durable_before_provider_reply() -> None:
    """A shadow saga captures the Agent output before Feishu receives it."""

    delivery_order: list[str] = []
    tracker = RuntimeDeliveryTaskTracker()
    run_context_store = delivery_context_store(
        {
            "run-1": {
                "agent_id": "agent-a",
                "trigger_source": "feishu",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "feishu:app:dm:ou_user",
                "shadow_saga_id": "saga-1",
                "kernel_message_id": "kmsg-1",
                "external_current_text": "好的，我查一下。",
            }
        }
    )

    def prepare(
        saga_id: str,
        run_id: str,
        output_kind: str,
        kernel_message_id: str | None,
        content: str,
    ) -> None:
        assert (saga_id, run_id, output_kind, kernel_message_id, content) == (
            "saga-1",
            "run-1",
            "intermediate",
            "kmsg-1",
            "好的，我查一下。",
        )
        delivery_order.append("durable")

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store=run_context_store,
        external_reply_sender=lambda _text, _metadata: delivery_order.append(
            "provider"
        ),
        shadow_output_prepare=prepare,
        task_tracker=tracker,
    )

    async def exercise() -> None:
        observer(
            {
                "event": "tool_start",
                "run_id": "run-1",
                "call_id": "call-1",
                "name": "read",
                "arguments": {},
            }
        )
        await tracker.drain_run("run-1")

    asyncio.run(exercise())

    assert delivery_order == ["durable", "provider"]


def test_im_shadow_visible_text_does_not_go_back_to_feishu() -> None:
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []
    sender = build_bg_reply_sender(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
    )
    reply_context = ReplyContext(
        channel_name="web_relay",
        target_chat_id="conv-shadow",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:app:dm:ou_user",
            "trigger_source": "im",
        },
    )

    asyncio.run(
        sender(
            "后台结果",
            reply_context,
            "agent-a|tool_call:sess-1:99",
        )
    )

    assert external == []
    assert manager.agent_messages == [
        {
            "text": "后台结果",
            "to": "conv-shadow",
            "from_session_id": "agent-a|tool_call:sess-1:99",
        }
    ]
