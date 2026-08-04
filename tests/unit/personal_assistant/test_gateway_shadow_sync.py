"""Shadow sync consumes canonical typed external conversation identity."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from personal_assistant.channels.base import (
    ExternalInboundEventIdentity,
    InboundMessage,
)
from personal_assistant.gateway.runtime_protocol import (
    ExternalConversationIdentity,
    RuntimeProtocolFacts,
    ShadowConversationRef,
    attach_runtime_protocol,
)
from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.runtime_delivery.task_tracker import (
    RuntimeDeliveryTaskTracker,
)
from personal_assistant.gateway.shadow_saga import (
    ExternalShadowBubbleEvent,
    ExternalShadowSagaStore,
)
from personal_assistant.gateway.shadow_sync import (
    IMShadowConversationSync,
    ShadowSyncPendingError,
)


def _build_sync(
    requests: list[dict[str, Any]],
    *,
    saga_store: ExternalShadowSagaStore | None = None,
) -> IMShadowConversationSync:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8")) if request.content else {}
        requests.append(
            {
                "path": request.url.path,
                "payload": payload,
                "idempotency_key": request.headers.get("Idempotency-Key"),
            }
        )
        if request.url.path == "/im/v1/me":
            return httpx.Response(200, json={"id": "owner-a"})
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            return httpx.Response(201, json={"id": "shadow-a"})
        if request.url.path == "/im/v1/conversations/shadow-a/messages":
            return httpx.Response(201, json={"id": "message-a"})
        if request.method == "PUT" and "/external-agent-messages/" in request.url.path:
            return httpx.Response(200, json={"id": "agent-rich-a"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    async def token_getter() -> str:
        return "token-a"

    return IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=token_getter,
        owner_user_id="owner-a",
        transport=httpx.MockTransport(handler),
        saga_store=saga_store,
    )


def _message(*, metadata: dict[str, Any] | None = None) -> InboundMessage:
    return InboundMessage(
        channel_name="feishu:agent-a",
        text="hello",
        external_user_id="external-user",
        external_chat_id="channel-owned-chat-id",
        is_group=True,
        agent_id="agent-a",
        metadata=metadata or {},
    )


def test_typed_only_external_identity_creates_shadow_conversation() -> None:
    requests: list[dict[str, Any]] = []
    sync = _build_sync(requests)
    inbound = attach_runtime_protocol(
        replace(
            _message(metadata={"chat_name": "Typed Team"}),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                conversation_type="group",
                trigger_source="external",
            )
        ),
    )

    shadow_ref = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert shadow_ref == ShadowConversationRef(
        conversation_id="shadow-a", im_message_id="message-a"
    )
    create_payload = requests[1]["payload"]
    assert create_payload["external_source"] == "feishu"
    assert create_payload["external_chat_id"] == "typed-chat-id"
    assert create_payload["title"] == "agent-a · Typed Team · feishu"
    assert "__runtime_protocol_facts__" not in create_payload["metadata"]
    assert requests[2]["idempotency_key"] == "shadow-user:feishu:app-a:event-a"


def test_durable_saga_reuses_confirmed_anchor_after_gateway_restart(
    tmp_path: Path,
) -> None:
    """A repeated provider event reads its durable IM anchor instead of writing again."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        replace(
            _message(metadata={"chat_name": "Typed Team"}),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                conversation_type="group",
                trigger_source="external",
            )
        ),
    )

    first = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))
    second = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert (
        first
        == second
        == ShadowConversationRef(conversation_id="shadow-a", im_message_id="message-a")
    )
    assert [request["path"] for request in requests].count(
        "/im/v1/conversations/external/find-or-create"
    ) == 1
    assert [request["path"] for request in requests].count(
        "/im/v1/conversations/shadow-a/messages"
    ) == 1
    saga = (
        saga_store.pending()[0]
        if saga_store.pending()
        else saga_store.require(first.shadow_saga_id or "")
    )
    assert requests[2]["idempotency_key"] == saga.shadow_user_idempotency_key


def test_recovery_replays_pending_durable_saga(tmp_path: Path) -> None:
    """A Gateway restart completes the user anchor recorded before IM became reachable."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        replace(
            _message(metadata={"chat_name": "Typed Team"}),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                conversation_type="group",
                trigger_source="external",
            )
        ),
    )
    saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")

    asyncio.run(sync.recover_pending())

    assert saga_store.pending() == ()
    assert [request["path"] for request in requests].count(
        "/im/v1/conversations/external/find-or-create"
    ) == 1
    assert [request["path"] for request in requests].count(
        "/im/v1/conversations/shadow-a/messages"
    ) == 1


def test_im_unavailable_after_saga_preparation_preserves_external_source_fact(
    tmp_path: Path,
) -> None:
    """Configured owner identity lets an offline external event become recoverable."""

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")

    def unavailable(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("IM unavailable")

    async def token_getter() -> str:
        return "token-a"

    sync = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=token_getter,
        owner_user_id="owner-a",
        transport=httpx.MockTransport(unavailable),
        saga_store=saga_store,
    )
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                conversation_type="group",
                trigger_source="external",
            )
        ),
    )

    with pytest.raises(ShadowSyncPendingError) as error:
        asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert saga_store.require(error.value.saga_id).shadow_ref is None


def test_durable_output_uses_kernel_identity_and_persists_im_ack(
    tmp_path: Path,
) -> None:
    """A replayed Kernel output retains one stable IM caller identity."""

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None

    first = saga_store.prepare_output(
        saga_id=saga.saga_id,
        run_id="run-1",
        output_kind="intermediate",
        kernel_message_id="kernel-message-1",
        content="working",
    )
    replay = saga_store.prepare_output(
        saga_id=saga.saga_id,
        run_id="run-1",
        output_kind="intermediate",
        kernel_message_id="kernel-message-1",
        content="working",
    )
    acknowledged = saga_store.record_output_anchor(
        output=first, im_message_id="agent-message-1"
    )

    assert replay.caller_idempotency_key == first.caller_idempotency_key
    assert acknowledged.im_message_id == "agent-message-1"
    assert saga_store.pending_outputs() == ()


def test_rich_bubble_snapshot_survives_reopen_with_shared_process_order(
    tmp_path: Path,
) -> None:
    """Gateway owns a complete terminal projection even when IM never saw live frames."""

    db_path = tmp_path / "shadow-sagas.sqlite3"
    saga_store = ExternalShadowSagaStore(db_path=db_path)
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None

    started = saga_store.record(
        ExternalShadowBubbleEvent(kind="begin", saga_id=saga.saga_id, run_id="run-1")
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="thinking",
            saga_id=saga.saga_id,
            run_id="run-1",
            thinking_text="inspect state",
        )
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="tool",
            saga_id=saga.saga_id,
            run_id="run-1",
            tool_call={
                "id": "call-1",
                "name": "read",
                "status": "running",
                "input": {"path": "a.py"},
            },
        )
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="tool",
            saga_id=saga.saga_id,
            run_id="run-1",
            tool_call={
                "id": "call-1",
                "name": "read",
                "status": "completed",
                "input": {"path": "a.py"},
                "output": "ok",
            },
        )
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text",
            saga_id=saga.saga_id,
            run_id="run-1",
            content="done",
            kernel_message_id="kernel-1",
        )
    )
    terminal = saga_store.record(
        ExternalShadowBubbleEvent(
            kind="terminal",
            saga_id=saga.saga_id,
            run_id="run-1",
            token_usage={"prompt": 10, "completion": 2, "total": 12},
            elapsed_ms=321,
            delivery_status="completed",
            kernel_message_id="kernel-1",
        )
    )

    reopened = ExternalShadowSagaStore(db_path=db_path)
    pending = reopened.pending_snapshots()

    assert terminal.shadow_message_id == started.shadow_message_id
    assert len(pending) == 1
    assert pending[0].state == "ready"
    assert pending[0].content == "done"
    assert pending[0].thinking == ({"seq": 0, "text": "inspect state"},)
    assert pending[0].tool_calls == (
        {
            "id": "call-1",
            "name": "read",
            "status": "completed",
            "input": {"path": "a.py"},
            "output": "ok",
            "seq": 1,
        },
    )
    assert pending[0].token_usage == {"prompt": 10, "completion": 2, "total": 12}
    assert pending[0].elapsed_ms == 321
    assert pending[0].kernel_message_id == "kernel-1"


def test_rich_bubble_identity_is_per_ordinal_and_only_terminal_is_pending(
    tmp_path: Path,
) -> None:
    """A multi-bubble run keeps one stable identity per visible bubble."""

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="slack",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None

    first = saga_store.record(
        ExternalShadowBubbleEvent(kind="begin", saga_id=saga.saga_id, run_id="run-1")
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text", saga_id=saga.saga_id, run_id="run-1", content="first"
        )
    )
    first_terminal = saga_store.record(
        ExternalShadowBubbleEvent(
            kind="terminal",
            saga_id=saga.saga_id,
            run_id="run-1",
            token_usage=None,
            delivery_status="completed",
        )
    )
    second = saga_store.record(
        ExternalShadowBubbleEvent(kind="begin", saga_id=saga.saga_id, run_id="run-1")
    )

    assert first_terminal.token_usage is None
    assert first.shadow_message_id != second.shadow_message_id
    assert [bubble.shadow_message_id for bubble in saga_store.pending_snapshots()] == [
        first.shadow_message_id
    ]

    discarded = saga_store.record(
        ExternalShadowBubbleEvent(kind="discard", saga_id=saga.saga_id, run_id="run-1")
    )
    assert discarded.state == "discarded"
    acknowledged = saga_store.acknowledge(
        shadow_message_id=first.shadow_message_id,
        im_message_id="im-agent-1",
    )
    assert acknowledged.state == "reconciled"
    assert acknowledged.im_message_id == "im-agent-1"
    assert saga_store.pending_snapshots() == ()


def test_terminal_snapshot_reconcile_uses_stable_identity_and_acknowledges(
    tmp_path: Path,
) -> None:
    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None
    saga_store.record_anchor(
        saga_id=saga.saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-a", im_message_id="user-message-a"
        ),
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text", saga_id=saga.saga_id, run_id="run-1", content="done"
        )
    )
    snapshot = saga_store.record(
        ExternalShadowBubbleEvent(
            kind="terminal",
            saga_id=saga.saga_id,
            run_id="run-1",
            delivery_status="completed",
            elapsed_ms=123,
        )
    )

    asyncio.run(sync.reconcile_snapshot(snapshot))

    request = requests[-1]
    assert request["path"].endswith(
        f"/external-agent-messages/{snapshot.shadow_message_id}"
    )
    assert request["payload"] == {
        "agent_id": "agent-a",
        "content": "done",
        "thinking": [],
        "tool_calls": [],
        "token_usage": None,
        "elapsed_ms": 123,
        "delivery_status": "completed",
        "kernel_message_id": None,
    }
    acknowledged = saga_store.require_snapshot(snapshot.shadow_message_id)
    assert acknowledged.state == "reconciled"
    assert acknowledged.im_message_id == "agent-rich-a"


def test_offline_observer_persists_complete_rich_terminal_snapshot(
    tmp_path: Path,
) -> None:
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="slack",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None
    context = {
        "run-1": {
            "agent_id": "agent-a",
            "trigger_source": "external",
            "reply_channel_name": "slack:agent-a",
            "reply_target_chat_id": "chat-a",
            "shadow_saga_id": saga.saga_id,
        }
    }
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store=context,
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
    )

    observer({"event": "run_status", "run_id": "run-1", "status": "running"})
    observer(
        {
            "event": "assistant_message",
            "run_id": "run-1",
            "message_id": "kernel-1",
            "content": "done",
            "reasoning_content": "inspect",
            "group_id": "round-1",
        }
    )
    observer(
        {
            "event": "tool_start",
            "run_id": "run-1",
            "call_id": "call-1",
            "name": "read",
            "arguments": {"path": "a.py"},
        }
    )
    observer(
        {
            "event": "tool_end",
            "run_id": "run-1",
            "call_id": "call-1",
            "name": "read",
            "arguments": {"path": "a.py"},
            "duration_ms": 20,
            "presentation": {"summary": "ok"},
        }
    )
    observer(
        {
            "event": "turn_end",
            "run_id": "run-1",
            "completed": True,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            "context_window": 100,
        }
    )

    snapshot = saga_store.pending_snapshots()[0]
    assert snapshot.content == "done"
    assert snapshot.thinking == ({"seq": 0, "text": "inspect"},)
    assert snapshot.tool_calls[0]["seq"] == 1
    assert snapshot.tool_calls[0]["status"] == "completed"
    assert snapshot.token_usage == {
        "prompt": 10,
        "completion": 2,
        "total": 12,
        "context_window": 100,
        "cache_read": 0,
        "cache_total_input": 0,
    }
    assert snapshot.elapsed_ms is not None
    assert snapshot.kernel_message_id == "kernel-1"


def test_online_observer_uses_one_shadow_identity_and_reconciles_after_ack(
    tmp_path: Path,
) -> None:
    class Manager:
        connected = True

        def __init__(self) -> None:
            self.frames: list[dict[str, Any]] = []

        async def send_json(self, _message_type: str, payload: dict[str, Any]) -> None:
            self.frames.append(dict(payload))

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            self.frames.append(dict(payload))
            if payload["kind"] == "turn_start":
                return {"payload": {"message_id": "im-agent-1"}}
            return {"payload": {"kind": payload["kind"]}}

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None
    manager = Manager()
    reconciled: list[str] = []
    task_tracker = RuntimeDeliveryTaskTracker()

    async def reconcile(snapshot) -> None:
        reconciled.append(snapshot.shadow_message_id)

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "conversation_id": "shadow-a",
                "trigger_source": "external",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": saga.saga_id,
            }
        },
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=reconcile,
        task_tracker=task_tracker,
    )

    async def emit() -> None:
        pending = observer(
            {"event": "run_status", "run_id": "run-1", "status": "running"}
        )
        assert pending is not None
        await pending
        pending = observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-1",
                "content": "done",
            }
        )
        assert pending is not None
        await pending
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await task_tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit())

    snapshot = saga_store.pending_snapshots()[0]
    assert [frame["kind"] for frame in manager.frames] == [
        "turn_start",
        "message_delta",
        "message_completed",
    ]
    assert manager.frames[0]["shadow_message_id"] == snapshot.shadow_message_id
    assert manager.frames[-1]["elapsed_ms"] == snapshot.elapsed_ms
    assert reconciled == [snapshot.shadow_message_id]
    assert saga_store.pending_outputs() == ()


def test_agent_output_is_mirrored_with_durable_idempotency_key(tmp_path: Path) -> None:
    """An Agent's external reply writes one recoverable IM mirror message."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None
    saga_store.record_anchor(
        saga_id=saga.saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-a", im_message_id="user-message-a"
        ),
    )

    asyncio.run(
        sync.mirror_agent_output(
            saga_id=saga.saga_id,
            run_id="run-1",
            output_kind="final",
            kernel_message_id="kernel-message-1",
            content="done",
        )
    )

    output_request = requests[-1]
    assert output_request["path"] == "/im/v1/conversations/shadow-a/messages"
    assert output_request["payload"] == {
        "sender": {"type": "agent", "id": "agent-a"},
        "content": "done",
        "suppress_relay": True,
    }
    assert output_request["idempotency_key"] == (
        f"shadow-agent:{saga.saga_id}:run-1:final:kernel-message-1"
    )
    assert saga_store.pending_outputs() == ()


def test_recovery_replays_pending_agent_output_after_gateway_restart(
    tmp_path: Path,
) -> None:
    """A durable Agent output is mirrored after restart once its user anchor exists."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None
    saga_store.record_anchor(
        saga_id=saga.saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-a", im_message_id="user-message-a"
        ),
    )
    pending = saga_store.prepare_output(
        saga_id=saga.saga_id,
        run_id="run-1",
        output_kind="final",
        kernel_message_id="kernel-message-1",
        content="done",
    )

    asyncio.run(sync.recover_pending())

    assert saga_store.pending_outputs() == ()
    assert requests[-1]["idempotency_key"] == pending.caller_idempotency_key


def test_runtime_observer_prepares_once_then_mirrors_same_output(
    tmp_path: Path,
) -> None:
    """External delivery passes the one durable output record to background mirroring."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="event-a"
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                trigger_source="external",
            )
        ),
    )
    saga = saga_store.prepare(message=inbound, agent_id="agent-a", owner_id="owner-a")
    assert saga is not None
    saga_store.record_anchor(
        saga_id=saga.saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-a", im_message_id="user-message-a"
        ),
    )
    tracker = RuntimeDeliveryTaskTracker()
    external_replies: list[str] = []
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "trigger_source": "feishu",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": saga.saga_id,
                "kernel_message_id": "kernel-message-1",
                "external_current_text": "done",
            }
        },
        external_reply_sender=lambda text, _metadata: external_replies.append(text),
        shadow_output_prepare=lambda saga_id, run_id, output_kind, kernel_message_id, content: (
            sync.prepare_agent_output(
                saga_id=saga_id,
                run_id=run_id,
                output_kind=output_kind,
                kernel_message_id=kernel_message_id,
                content=content,
            )
        ),
        shadow_output_mirror=sync.mirror_prepared_agent_output,
        task_tracker=tracker,
    )

    async def emit_and_drain() -> None:
        observer(
            {
                "event": "tool_start",
                "run_id": "run-1",
                "call_id": "call-1",
                "name": "read",
                "arguments": {},
            }
        )
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit_and_drain())

    assert external_replies == ["done"]
    assert saga_store.pending_outputs() == ()
    assert [request["path"] for request in requests] == [
        "/im/v1/conversations/shadow-a/messages"
    ]
    assert requests[0]["idempotency_key"] == (
        f"shadow-agent:{saga.saga_id}:run-1:intermediate:kernel-message-1"
    )


def test_missing_provider_event_identity_records_durable_diagnostic(
    tmp_path: Path,
) -> None:
    """An external message without a provider identity cannot silently enter a saga."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    inbound = attach_runtime_protocol(
        _message(),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="typed-chat-id",
                agent_id="agent-a",
                conversation_type="group",
                trigger_source="external",
            )
        ),
    )

    shadow_ref = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert shadow_ref is None
    assert requests == []
    assert saga_store.diagnostic_reasons() == ("shadow_identity_unavailable",)


def test_typed_im_origin_is_rejected_by_shadow_adapter() -> None:
    requests: list[dict[str, Any]] = []
    sync = _build_sync(requests)
    inbound = attach_runtime_protocol(
        _message(
            metadata={
                "external_source": "feishu",
                "external_chat_id": "legacy-would-sync",
            }
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="im",
                external_chat_id="conversation-a",
                agent_id="agent-a",
                trigger_source="im",
            )
        ),
    )

    shadow_ref = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert shadow_ref is None
    assert requests == []


def test_legacy_external_metadata_without_provider_identity_skips_shadow() -> None:
    requests: list[dict[str, Any]] = []
    sync = _build_sync(requests)
    inbound = _message(
        metadata={
            "external_source": "slack",
            "external_chat_id": "legacy-chat-id",
            "conversation_type": "group",
            "chat_name": "Legacy Team",
        }
    )

    shadow_ref = asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert shadow_ref is None
    assert requests == []
