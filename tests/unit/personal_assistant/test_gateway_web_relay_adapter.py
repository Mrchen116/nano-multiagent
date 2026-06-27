"""Unit tests for WebRelayAdapter: relay payload conversion and dedup integration."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import dataclasses

from personal_assistant.channels.base import (
    InboundMessage,
    OutboundMessage,
    ReplyContext,
)
from personal_assistant.channels.web_relay_adapter import (
    RelayDeduplicationStore,
    WebRelayAdapter,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter


def test_web_relay_adapter_converts_relay_payload_to_inbound_message() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)

    inbound = adapter.accept_relay(
        {
            "relay_task_id": "relay-1",
            "idempotency_key": "idem-1",
            "agent_id": "agent-a",
            "message": {
                "id": "msg-1",
                "sender_user_id": "user-1",
                "conversation_id": "conv-1",
                "content": "hello gateway",
            },
            "metadata": {"conversation_type": "group", "thread_id": "thread-1"},
        }
    )

    assert inbound == seen[0]
    assert inbound.channel_name == "web_relay"
    assert inbound.external_chat_id == "conv-1"
    assert inbound.is_group is True
    assert inbound.metadata["relay_task_id"] == "relay-1"
    assert inbound.metadata["message_id"] == "msg-1"

    adapter.send(
        OutboundMessage(
            channel_name="web_relay",
            text="reply",
            target_chat_id="conv-1",
        )
    )
    assert adapter.sent[0].text == "reply"


def test_web_relay_adapter_uses_dedup_store_on_accept(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")
    adapter = WebRelayAdapter(dedup_store=store)
    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    payload = {
        "relay_task_id": "relay-1",
        "idempotency_key": "idem-1",
        "message": {
            "id": "msg-1",
            "sender_user_id": "user-1",
            "conversation_id": "conv-1",
            "content": "hello gateway",
        },
        "metadata": {"conversation_type": "direct"},
    }

    adapter.accept_relay(payload)
    adapter.accept_relay(payload)

    assert [item.text for item in seen] == ["hello gateway"]
    reloaded = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")
    reloaded.load_from_db()
    assert reloaded.contains("idem-1") is True


def test_web_relay_adapter_loads_store_on_start(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    seeded = RelayDeduplicationStore(db_path=db_path)
    seeded.add("idem-1")
    adapter = WebRelayAdapter(dedup_store=RelayDeduplicationStore(db_path=db_path))

    adapter.start(lambda _message: None)

    assert adapter._seen_idempotency_keys == deque(["idem-1"])  # noqa: SLF001


def test_web_relay_adapter_without_store_uses_in_memory_dedup() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    payload = {
        "relay_task_id": "relay-1",
        "idempotency_key": "idem-1",
        "message": {
            "id": "msg-1",
            "sender_user_id": "user-1",
            "conversation_id": "conv-1",
            "content": "hello gateway",
        },
        "metadata": {"conversation_type": "direct"},
    }

    adapter.accept_relay(payload)
    adapter.accept_relay(payload)

    assert [item.text for item in seen] == ["hello gateway"]


def test_external_channel_outbound_excludes_thinking() -> None:
    """feat-439-M2 (verifier WARNING-1): 外部 channel 出站只见正文，绝不带 thinking。

    锁死 spec「外部 IM 不暴露 thinking」：一轮回合带 reasoning_content，但出站到外部
    channel 的 OutboundMessage 只承载内核回复正文（pipeline 出站口径取 ``content``），
    既无 thinking/reasoning 字段，序列化也不含思考文本。
    """
    # 结构契约：OutboundMessage 没有任何思考/推理字段。
    field_names = {f.name for f in dataclasses.fields(OutboundMessage)}
    assert not any(("think" in n) or ("reason" in n) for n in field_names), field_names

    # 行为：模拟一轮带思考的回合，出站文本取 content（与 inbound_pipeline 一致）。
    assistant_event = {
        "event": "assistant_message",
        "content": "这一轮缓存命中率约 87%。",
        "reasoning_content": "内部思考绝不可外泄：先看 types.py 再归一口径……",
    }
    reply_text = str(assistant_event.get("content") or "")

    adapter = WebRelayAdapter()
    adapter.start(lambda _m: None)
    router = OutboundRouter(ChannelRegistry([adapter]))

    outbound = router.send_text(
        text=reply_text,
        reply_context=ReplyContext(
            channel_name="web_relay",
            target_chat_id="conv-1",
        ),
    )

    assert outbound.text == "这一轮缓存命中率约 87%。"
    # 出站对象任何字段序列化都不含思考文本（防未来把 reasoning 拼进 text / 加字段）。
    serialized = repr(dataclasses.asdict(outbound))
    assert "内部思考" not in serialized
    assert "reasoning" not in serialized
    assert adapter.sent[-1].text == reply_text
    assert "内部思考" not in adapter.sent[-1].text
