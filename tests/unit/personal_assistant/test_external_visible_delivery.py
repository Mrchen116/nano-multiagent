"""External-channel user-visible delivery boundaries for feat-447 M14."""

from __future__ import annotations

import asyncio
from typing import Any

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.session_keys import SessionBindingStore
from personal_assistant.main import (
    _build_bg_reply_sender,
    _build_kernel_event_observer,
    _build_session_event_callback,
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


def test_feishu_visible_control_text_goes_to_external_and_shadow_im() -> None:
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []

    def _external_sender(text: str, metadata: dict[str, str]) -> None:
        external.append((text, dict(metadata)))

    sender = _build_bg_reply_sender(
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
    sender = _build_bg_reply_sender(
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
    run_context_store = {
        "run-1": {
            "agent_id": "agent-a",
            "trigger_source": "feishu",
            "reply_channel_name": "feishu:agent-a",
            "reply_target_chat_id": "feishu:app:dm:ou_user",
            "reply_thread_id": "om_trigger",
        }
    }
    observer = _build_kernel_event_observer(
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


def test_im_shadow_visible_text_does_not_go_back_to_feishu() -> None:
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []
    sender = _build_bg_reply_sender(
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
    store = SessionBindingStore()
    store.bind(
        session_key="feishu:chat:agent-a",
        kernel_session_id="sess-1",
        reply_context=ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:app:dm:ou_user",
            metadata={
                "external_source": "feishu",
                "external_chat_id": "feishu:app:dm:ou_user",
                "trigger_source": "feishu",
                "shadow_conversation_id": "conv-shadow",
            },
        ),
    )
    callback = _build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        session_store=store,
    )

    asyncio.run(
        callback(
            "sess-1",
            {
                "event": "self_evolution_review",
                "reviewed_skills": True,
                "reviewed_memory": False,
            },
        )
    )

    assert manager.json_messages == [
        (
            "node.system_message",
            {
                "conversation_id": "conv-shadow",
                "text": "· background self-evolution review: skills updated",
            },
        )
    ]
