"""Unit tests for WebRelayAdapter: relay payload conversion and dedup integration."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Thread

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
    assert inbound.metadata["conversation_id"] == "conv-1"
    assert inbound.ingress.im_relay is not None
    assert inbound.ingress.im_relay.relay_task_id == "relay-1"
    assert inbound.ingress.im_relay.idempotency_key == "idem-1"
    assert inbound.ingress.im_relay.im_message_id == "msg-1"
    assert inbound.ingress.external_conversation is None
    assert inbound.ingress.external_event is None

    adapter.send(
        OutboundMessage(
            channel_name="web_relay",
            text="reply",
            target_chat_id="conv-1",
        )
    )
    assert adapter.sent[0].text == "reply"


def test_web_relay_adapter_accepts_top_level_conversation_id() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)

    inbound = adapter.accept_relay(
        {
            "relay_task_id": "relay-top-level-conv",
            "idempotency_key": "idem-top-level-conv",
            "conversation_id": "conv-top-level",
            "agent_id": "agent-a",
            "message": {
                "id": "msg-1",
                "sender_user_id": "user-1",
                "content": "hello gateway",
            },
            "metadata": {},
        }
    )

    assert inbound == seen[0]
    assert inbound.external_chat_id == "conv-top-level"
    assert inbound.ingress.im_relay is not None
    assert inbound.ingress.im_relay.relay_task_id == "relay-top-level-conv"


def test_web_relay_adapter_preserves_shadow_identity_and_group_target_agent() -> None:
    """Shadow relay metadata drives external session identity while delivery stays on IM id."""
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)

    inbound = adapter.accept_relay(
        {
            "relay_task_id": "relay-shadow",
            "idempotency_key": "idem-shadow",
            "agent_id": "plato",
            "message": {
                "id": "msg-shadow",
                "sender_user_id": "owner-user",
                "conversation_id": "im-conv-shadow",
                "content": "summarize the feishu background",
            },
            "metadata": {
                "trigger_source": "im",
                "conversation_type": "group",
                "external_source": "feishu",
                "external_chat_id": "oc_product",
                "agent_id": "plato",
            },
        }
    )

    assert inbound == seen[0]
    assert inbound.channel_name == "web_relay"
    assert inbound.external_chat_id == "im-conv-shadow"
    assert inbound.is_group is True
    assert inbound.agent_id == "plato"
    assert inbound.metadata["trigger_source"] == "im"
    assert inbound.metadata["external_source"] == "feishu"
    assert inbound.metadata["external_chat_id"] == "oc_product"
    assert inbound.metadata["agent_id"] == "plato"
    assert inbound.metadata["mentioned_agent_ids"] == ["plato"]
    assert inbound.metadata["implicit_external_agent_target"] is True


def test_web_relay_adapter_returns_callback_message_with_typed_ingress() -> None:
    """The adapter callback value is the complete normalized ingress value."""
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)

    inbound = adapter.accept_relay(
        {
            "relay_task_id": "relay-shadow",
            "idempotency_key": "idem-shadow",
            "agent_id": "plato",
            "message": {
                "id": "msg-shadow",
                "sender_user_id": "owner-user",
                "conversation_id": "im-conv-shadow",
                "content": "summarize the feishu background",
            },
            "metadata": {
                "trigger_source": "im",
                "conversation_type": "group",
                "external_source": "feishu",
                "external_chat_id": "oc_product",
                "agent_id": "plato",
            },
        }
    )

    assert seen == [inbound]
    assert inbound.ingress.im_relay is not None
    assert inbound.ingress.im_relay.relay_task_id == "relay-shadow"
    assert inbound.ingress.im_relay.idempotency_key == "idem-shadow"
    assert inbound.ingress.im_relay.im_message_id == "msg-shadow"
    assert inbound.ingress.external_conversation is not None
    assert inbound.ingress.external_conversation.external_source == "feishu"
    assert inbound.ingress.external_conversation.external_chat_id == "oc_product"
    assert inbound.ingress.external_conversation.trigger_source == "im"
    assert inbound.ingress.external_event is None


def test_outbound_router_dedupes_by_reply_dedupe_key() -> None:
    class _Adapter:
        name = "feishu:agent-a"

        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []

        def start(self, _on_inbound) -> None:  # noqa: ANN001
            return None

        def send(self, outbound: OutboundMessage) -> None:
            self.sent.append(outbound)

        def stop(self) -> None:
            return None

    adapter = _Adapter()
    router = OutboundRouter(ChannelRegistry([adapter]))
    context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:cli_a:dm:ou_user",
        metadata={"reply_dedupe_key": "run-1:text:Final answer."},
    )

    first = router.send_text(text="Final answer.", reply_context=context)
    second = router.send_text(text="Final answer.", reply_context=context)

    assert first is not None
    assert second is None
    assert [item.text for item in adapter.sent] == ["Final answer."]


def test_outbound_router_bounds_dedupe_key_memory() -> None:
    class _Adapter:
        name = "feishu:agent-a"

        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []

        def start(self, _on_inbound) -> None:  # noqa: ANN001
            return None

        def send(self, outbound: OutboundMessage) -> None:
            self.sent.append(outbound)

        def stop(self) -> None:
            return None

    adapter = _Adapter()
    router = OutboundRouter(ChannelRegistry([adapter]), max_dedupe_keys=1)

    router.send_text(
        text="first",
        reply_context=ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:cli_a:dm:ou_user",
            metadata={"reply_dedupe_key": "run-1:text:first"},
        ),
    )
    router.send_text(
        text="second",
        reply_context=ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:cli_a:dm:ou_user",
            metadata={"reply_dedupe_key": "run-2:text:second"},
        ),
    )
    replay_after_eviction = router.send_text(
        text="first",
        reply_context=ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:cli_a:dm:ou_user",
            metadata={"reply_dedupe_key": "run-1:text:first"},
        ),
    )

    assert replay_after_eviction is not None
    assert [item.text for item in adapter.sent] == ["first", "second", "first"]


def test_outbound_router_dedupes_concurrent_external_final_reply_paths() -> None:
    class _BlockingAdapter:
        name = "feishu:agent-a"

        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []
            self.send_started = Event()
            self.allow_send_to_return = Event()

        def start(self, _on_inbound) -> None:  # noqa: ANN001
            return None

        def send(self, outbound: OutboundMessage) -> None:
            self.sent.append(outbound)
            self.send_started.set()
            assert self.allow_send_to_return.wait(timeout=1)

        def stop(self) -> None:
            return None

    adapter = _BlockingAdapter()
    router = OutboundRouter(ChannelRegistry([adapter]))
    mirrored_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:cli_a:dm:ou_user",
        metadata={
            "reply_phase": "final",
            "reply_dedupe_key": "run-1:bubble:kmsg-1",
        },
    )
    terminal_context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:cli_a:dm:ou_user",
        metadata={
            "reply_phase": "final",
            "reply_dedupe_key": "run-1:text:Final answer.",
        },
    )
    results: list[OutboundMessage | None] = []

    mirror_thread = Thread(
        target=lambda: results.append(
            router.send_text(text="Final answer.", reply_context=mirrored_context)
        )
    )
    mirror_thread.start()
    assert adapter.send_started.wait(timeout=1)

    terminal_finished = Event()

    def _send_terminal() -> None:
        try:
            results.append(
                router.send_text(text="Final answer.", reply_context=terminal_context)
            )
        finally:
            terminal_finished.set()

    terminal_thread = Thread(target=_send_terminal)
    terminal_thread.start()
    try:
        # A reserved semantic key lets the fallback return while the mirror send
        # remains held; the baseline blocks here until both sends complete.
        assert terminal_finished.wait(timeout=0.2)
    finally:
        adapter.allow_send_to_return.set()
        mirror_thread.join(timeout=1)
        terminal_thread.join(timeout=1)

    assert not mirror_thread.is_alive()
    assert not terminal_thread.is_alive()
    assert len([result for result in results if result is not None]) == 1
    assert [item.text for item in adapter.sent] == ["Final answer."]


def test_outbound_router_releases_dedupe_reservation_after_send_failure() -> None:
    class _FailOnceAdapter:
        name = "feishu:agent-a"

        def __init__(self) -> None:
            self.attempts = 0
            self.sent: list[OutboundMessage] = []

        def start(self, _on_inbound) -> None:  # noqa: ANN001
            return None

        def send(self, outbound: OutboundMessage) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("provider unavailable")
            self.sent.append(outbound)

        def stop(self) -> None:
            return None

    adapter = _FailOnceAdapter()
    router = OutboundRouter(ChannelRegistry([adapter]))
    context = ReplyContext(
        channel_name="feishu:agent-a",
        target_chat_id="feishu:cli_a:dm:ou_user",
        metadata={"reply_dedupe_key": "run-1:text:retryable"},
    )

    try:
        router.send_text(text="retryable", reply_context=context)
    except RuntimeError as error:
        assert str(error) == "provider unavailable"
    else:
        raise AssertionError("provider failure must propagate")
    retried = router.send_text(text="retryable", reply_context=context)

    assert retried is not None
    assert [item.text for item in adapter.sent] == ["retryable"]


def test_outbound_router_dedupes_external_final_reply_across_paths() -> None:
    class _Adapter:
        name = "feishu:agent-a"

        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []

        def start(self, _on_inbound) -> None:  # noqa: ANN001
            return None

        def send(self, outbound: OutboundMessage) -> None:
            self.sent.append(outbound)

        def stop(self) -> None:
            return None

    adapter = _Adapter()
    router = OutboundRouter(ChannelRegistry([adapter]))

    mirrored = router.send_text(
        text="Final answer.",
        reply_context=ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:cli_a:dm:ou_user",
            metadata={
                "reply_phase": "final",
                "reply_dedupe_key": "run-1:bubble:kmsg-1",
            },
        ),
    )
    terminal = router.send_text(
        text="Final answer.",
        reply_context=ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="feishu:cli_a:dm:ou_user",
            metadata={
                "reply_phase": "final",
                "reply_dedupe_key": "run-1:text:Final answer.",
            },
        ),
    )

    assert mirrored is not None
    assert terminal is None
    assert [item.text for item in adapter.sent] == ["Final answer."]


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

    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    adapter.accept_relay(
        {
            "relay_task_id": "relay-1",
            "idempotency_key": "idem-1",
            "message": {
                "id": "msg-1",
                "sender_user_id": "user-1",
                "conversation_id": "conv-1",
                "content": "must stay deduplicated after restart",
            },
            "metadata": {"conversation_type": "direct"},
        }
    )

    assert seen == []


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
