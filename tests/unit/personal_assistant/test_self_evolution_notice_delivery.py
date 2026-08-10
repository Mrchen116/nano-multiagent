"""Trigger-source delivery for truthful self-evolution update receipts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.runtime_delivery.background import (
    build_session_event_callback,
)


class _FakeIMManager:
    connected = True

    def __init__(self, *, ack: object = None) -> None:
        self.json_messages: list[tuple[str, dict[str, Any]]] = []
        self.ack = {"message_id": "notice-1"} if ack is None else ack

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.json_messages.append((message_type, dict(payload)))
        if isinstance(self.ack, Exception):
            raise self.ack
        return dict(self.ack)


def _context(
    *,
    trigger_source: str,
    target_chat_id: str = "feishu:app:dm:ou_user",
    shadow_conversation_id: str = "conv-shadow",
) -> ReplyContext:
    if trigger_source == "im":
        return ReplyContext(
            channel_name="web_relay",
            target_chat_id=shadow_conversation_id,
            metadata={
                "external_source": "feishu",
                "trigger_source": "im",
                "shadow_conversation_id": shadow_conversation_id,
            },
        )
    return ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id=target_chat_id,
        metadata={
            "external_source": "feishu",
            "trigger_source": "feishu",
            "shadow_conversation_id": shadow_conversation_id,
            "feishu_message_id": "om_origin",
        },
    )


def _event(sequence: int, *targets: str) -> dict[str, Any]:
    return {
        "event": "self_evolution_review",
        "updated_targets": list(targets),
        "reviewed_skills": "skills" in targets,
        "reviewed_memory": "memory" in targets,
        "_id": sequence,
    }


def test_feishu_review_sends_one_receipt_to_original_chat_and_shadow() -> None:
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
        delivery_incarnation="gateway-run-1",
    )

    asyncio.run(
        callback(
            _context(trigger_source="feishu"), "agent-a", "sess-1", _event(87, "skills")
        )
    )

    identity = "self-evolution-review:gateway-run-1:sess-1:87"
    assert external == [
        (
            "· background self-evolution review: skills updated",
            {
                "channel_name": "feishu:agent-a",
                "target_chat_id": "feishu:app:dm:ou_user",
                "reply_phase": "intermediate",
                "reply_dedupe_key": identity,
                "feishu_message_id": "om_origin",
            },
        )
    ]
    assert manager.json_messages == [
        (
            "node.system_message",
            {
                "conversation_id": "conv-shadow",
                "idempotency_key": identity,
                "text": "· background self-evolution review: skills updated",
                "system_notice": {
                    "kind": "self_evolution_review",
                    "source_agent_id": "agent-a",
                    "updated_targets": ["skills"],
                },
            },
        )
    ]


def test_origin_switching_uses_each_event_route_without_latest_binding_fallback() -> (
    None
):
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
        delivery_incarnation="gateway-run-1",
    )

    asyncio.run(
        callback(
            _context(
                trigger_source="feishu",
                target_chat_id="chat-first",
                shadow_conversation_id="shadow-first",
            ),
            "agent-a",
            "sess-1",
            _event(91, "memory"),
        )
    )
    asyncio.run(
        callback(
            _context(trigger_source="im", shadow_conversation_id="shadow-second"),
            "agent-a",
            "sess-1",
            _event(92, "skills"),
        )
    )
    asyncio.run(
        callback(
            _context(
                trigger_source="feishu",
                target_chat_id="chat-third",
                shadow_conversation_id="shadow-third",
            ),
            "agent-a",
            "sess-1",
            _event(93, "skills", "memory"),
        )
    )

    assert [metadata["target_chat_id"] for _, metadata in external] == [
        "chat-first",
        "chat-third",
    ]
    assert [payload["conversation_id"] for _, payload in manager.json_messages] == [
        "shadow-first",
        "shadow-second",
        "shadow-third",
    ]


def test_replayed_notice_uses_the_same_external_and_shadow_identity() -> None:
    manager = _FakeIMManager()
    external: list[tuple[str, dict[str, str]]] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
        delivery_incarnation="gateway-run-1",
    )
    context = _context(trigger_source="feishu")
    event = _event(94, "memory")

    asyncio.run(callback(context, "agent-a", "sess-1", event))
    asyncio.run(callback(context, "agent-a", "sess-1", dict(event)))

    assert [metadata["reply_dedupe_key"] for _, metadata in external] == [
        "self-evolution-review:gateway-run-1:sess-1:94",
        "self-evolution-review:gateway-run-1:sess-1:94",
    ]
    assert [payload["idempotency_key"] for _, payload in manager.json_messages] == [
        "self-evolution-review:gateway-run-1:sess-1:94",
        "self-evolution-review:gateway-run-1:sess-1:94",
    ]


def test_missing_im_manager_does_not_block_external_notice() -> None:
    external: list[tuple[str, dict[str, str]]] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: None,
        external_reply_sender=lambda text, metadata: external.append(
            (text, dict(metadata))
        ),
        delivery_incarnation="gateway-run-1",
    )

    asyncio.run(
        callback(
            _context(trigger_source="feishu"),
            "agent-a",
            "sess-1",
            _event(95, "memory"),
        )
    )

    assert len(external) == 1


def test_external_failure_does_not_block_shadow_notice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = _FakeIMManager()

    def _fail_external(_text: str, _metadata: dict[str, str]) -> None:
        raise RuntimeError("provider unavailable")

    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=_fail_external,
        delivery_incarnation="gateway-run-1",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.gateway.runtime_delivery.background",
    ):
        asyncio.run(
            callback(
                _context(trigger_source="feishu"),
                "agent-a",
                "sess-1",
                _event(96, "skills"),
            )
        )

    assert len(manager.json_messages) == 1
    assert "external delivery failed" in caplog.text


@pytest.mark.parametrize("ack", [RuntimeError("rejected"), {}, {"message_id": " "}])
def test_shadow_failure_does_not_block_external_notice(
    caplog: pytest.LogCaptureFixture, ack: object
) -> None:
    manager = _FakeIMManager(ack=ack)
    external: list[str] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=lambda text, _metadata: external.append(text),
        delivery_incarnation="gateway-run-1",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="personal_assistant.gateway.runtime_delivery.background",
    ):
        asyncio.run(
            callback(
                _context(trigger_source="feishu"),
                "agent-a",
                "sess-1",
                _event(97, "memory"),
            )
        )

    assert external == ["· background self-evolution review: memory updated"]
    assert "delivery failed" in caplog.text


@pytest.mark.parametrize(
    "event",
    [
        {"event": "self_evolution_review", "updated_targets": [], "_id": 98},
        {"event": "self_evolution_review", "updated_targets": ["memory"]},
        {"event": "future_notice", "updated_targets": ["memory"], "_id": 99},
    ],
)
def test_empty_unsequenced_or_future_notice_does_not_reach_either_exit(
    event: dict[str, Any],
) -> None:
    manager = _FakeIMManager()
    external: list[str] = []
    callback = build_session_event_callback(
        im_connection_manager_factory=lambda: manager,
        external_reply_sender=lambda text, _metadata: external.append(text),
    )

    asyncio.run(callback(_context(trigger_source="feishu"), "agent-a", "sess-1", event))

    assert external == []
    assert manager.json_messages == []
