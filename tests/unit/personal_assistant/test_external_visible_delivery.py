"""External-channel user-visible delivery boundaries for feat-447 M14."""

from __future__ import annotations

from tests.helpers.runtime_delivery import delivery_context_store
import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.runtime_delivery.background import (
    build_bg_reply_sender,
    build_session_event_callback,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)


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
    )

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


def test_external_output_is_durable_before_provider_reply() -> None:
    """A shadow saga captures the Agent output before Feishu receives it."""

    delivery_order: list[str] = []
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


def test_system_notification_for_feishu_binding_targets_shadow_im_only() -> None:
    manager = _FakeIMManager()
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
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        delivery_incarnation="gateway-run-1",
    )

    asyncio.run(
        callback(
            reply_context,
            "agent-a",
            "sess-1",
            {
                "event": "self_evolution_review",
                "reviewed_skills": True,
                "reviewed_memory": False,
                "_id": 87,
            },
        )
    )

    assert manager.json_messages == [
        (
            "node.system_message",
            {
                "conversation_id": "conv-shadow",
                "idempotency_key": ("self-evolution-review:gateway-run-1:sess-1:87"),
                "text": "· background self-evolution review: skills updated",
                "system_notice": {
                    "kind": "self_evolution_review",
                    "source_agent_id": "agent-a",
                    "updated_targets": ["skills"],
                },
            },
        )
    ]


def test_system_notification_skips_empty_review_and_unsequenced_event() -> None:
    manager = _FakeIMManager()
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
    )
    reply_context = ReplyContext(channel_name="web_relay", target_chat_id="conv-1")

    asyncio.run(
        callback(
            reply_context,
            "agent-a",
            "sess-1",
            {"event": "self_evolution_review", "_id": 88},
        )
    )
    asyncio.run(
        callback(
            reply_context,
            "agent-a",
            "sess-1",
            {
                "event": "self_evolution_review",
                "reviewed_memory": True,
            },
        )
    )

    assert manager.json_messages == []


def test_system_notification_identity_is_stable_per_gateway_incarnation() -> None:
    manager = _FakeIMManager()
    context = ReplyContext(channel_name="web_relay", target_chat_id="conv-1")
    event = {
        "event": "self_evolution_review",
        "reviewed_memory": True,
        "_id": 87,
    }
    first = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        delivery_incarnation="gateway-run-1",
    )
    restarted = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        delivery_incarnation="gateway-run-2",
    )

    asyncio.run(first(context, "agent-a", "sess-1", event))
    asyncio.run(first(context, "agent-a", "sess-1", event))
    asyncio.run(restarted(context, "agent-a", "sess-1", event))

    keys = [payload["idempotency_key"] for _, payload in manager.json_messages]
    assert keys == [
        "self-evolution-review:gateway-run-1:sess-1:87",
        "self-evolution-review:gateway-run-1:sess-1:87",
        "self-evolution-review:gateway-run-2:sess-1:87",
    ]


def test_system_notification_queues_while_im_is_disconnected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = _FakeIMManager()
    manager.connected = False
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        delivery_incarnation="gateway-run-1",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.gateway.runtime_delivery.background",
    ):
        asyncio.run(
            callback(
                ReplyContext(channel_name="web_relay", target_chat_id="conv-1"),
                "agent-a",
                "sess-1",
                {
                    "event": "self_evolution_review",
                    "reviewed_skills": True,
                    "_id": 88,
                },
            )
        )

    assert [message_type for message_type, _ in manager.json_messages] == [
        "node.system_message"
    ]
    assert "queued while IM is disconnected" in caplog.text
    assert "conv-1" in caplog.text
    assert "agent-a" in caplog.text


def test_system_notification_logs_missing_manager(
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: None,
        delivery_incarnation="gateway-run-1",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.gateway.runtime_delivery.background",
    ):
        asyncio.run(
            callback(
                ReplyContext(channel_name="web_relay", target_chat_id="conv-1"),
                "agent-a",
                "sess-1",
                {
                    "event": "self_evolution_review",
                    "reviewed_memory": True,
                    "_id": 89,
                },
            )
        )

    assert "has no IM connection manager" in caplog.text
    assert "conv-1" in caplog.text
    assert "agent-a" in caplog.text


@pytest.mark.parametrize("ack", [RuntimeError("rejected"), {}, {"message_id": " "}])
def test_system_notification_logs_negative_or_malformed_ack(
    caplog: pytest.LogCaptureFixture, ack: object
) -> None:
    class _AckManager(_FakeIMManager):
        async def send_json_await_ack(
            self, message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            self.json_messages.append((message_type, dict(payload)))
            if isinstance(ack, Exception):
                raise ack
            return dict(ack)

    manager = _AckManager()
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        delivery_incarnation="gateway-run-1",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.gateway.runtime_delivery.background",
    ):
        asyncio.run(
            callback(
                ReplyContext(channel_name="web_relay", target_chat_id="conv-1"),
                "agent-a",
                "sess-1",
                {
                    "event": "self_evolution_review",
                    "reviewed_memory": True,
                    "_id": 90,
                },
            )
        )

    assert "delivery failed" in caplog.text
    assert "sequence=90" in caplog.text
