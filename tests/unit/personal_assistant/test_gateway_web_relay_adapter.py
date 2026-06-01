"""Unit tests for WebRelayAdapter: relay payload conversion and dedup integration."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.channels.web_relay_adapter import (
    RelayDeduplicationStore,
    WebRelayAdapter,
)


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
