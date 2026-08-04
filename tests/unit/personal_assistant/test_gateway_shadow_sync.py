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
from personal_assistant.gateway.runtime_delivery.context import (
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
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
        if request.url.path == "/im/v1/nodes":
            return httpx.Response(
                200, json=[{"node_id": "node-a", "owner_id": "owner-a"}]
            )
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
        node_id="node-a",
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
    assert requests[3]["idempotency_key"] == saga.shadow_user_idempotency_key


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


def test_recovery_interleaves_each_user_anchor_with_its_agent_snapshots(
    tmp_path: Path,
) -> None:
    """Two fully offline turns recover in user/Agent conversational order."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    shadow_message_ids: list[str] = []
    for ordinal in (1, 2):
        inbound = attach_runtime_protocol(
            replace(
                _message(),
                text=f"question {ordinal}",
                external_event_identity=ExternalInboundEventIdentity(
                    connector_account_id="app-a",
                    provider_event_id=f"event-{ordinal}",
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
        saga = saga_store.prepare(
            message=inbound, agent_id="agent-a", owner_id="owner-a"
        )
        assert saga is not None
        saga_store.record(
            ExternalShadowBubbleEvent(
                kind="begin", saga_id=saga.saga_id, run_id=f"run-{ordinal}"
            )
        )
        snapshot = saga_store.record(
            ExternalShadowBubbleEvent(
                kind="text",
                saga_id=saga.saga_id,
                run_id=f"run-{ordinal}",
                content=f"answer {ordinal}",
            )
        )
        saga_store.record(
            ExternalShadowBubbleEvent(
                kind="terminal",
                saga_id=saga.saga_id,
                run_id=f"run-{ordinal}",
                delivery_status="completed",
            )
        )
        shadow_message_ids.append(snapshot.shadow_message_id)

    asyncio.run(sync.recover_pending())

    assert [request["path"] for request in requests] == [
        "/im/v1/me",
        "/im/v1/nodes",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/shadow-a/messages",
        f"/im/v1/conversations/shadow-a/external-agent-messages/{shadow_message_ids[0]}",
        "/im/v1/nodes",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/shadow-a/messages",
        f"/im/v1/conversations/shadow-a/external-agent-messages/{shadow_message_ids[1]}",
    ]


def test_recovery_preserves_order_when_first_user_anchor_already_exists(
    tmp_path: Path,
) -> None:
    """An anchored first turn still recovers before a fully-offline second turn."""

    requests: list[dict[str, Any]] = []
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sync = _build_sync(requests, saga_store=saga_store)
    sagas = []
    shadow_message_ids: list[str] = []
    for ordinal in (1, 2):
        inbound = attach_runtime_protocol(
            replace(
                _message(),
                text=f"question {ordinal}",
                external_event_identity=ExternalInboundEventIdentity(
                    connector_account_id="app-a",
                    provider_event_id=f"mixed-event-{ordinal}",
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
        saga = saga_store.prepare(
            message=inbound, agent_id="agent-a", owner_id="owner-a"
        )
        assert saga is not None
        sagas.append(saga)
        saga_store.record(
            ExternalShadowBubbleEvent(
                kind="begin", saga_id=saga.saga_id, run_id=f"mixed-run-{ordinal}"
            )
        )
        snapshot = saga_store.record(
            ExternalShadowBubbleEvent(
                kind="text",
                saga_id=saga.saga_id,
                run_id=f"mixed-run-{ordinal}",
                content=f"answer {ordinal}",
            )
        )
        saga_store.record(
            ExternalShadowBubbleEvent(
                kind="terminal",
                saga_id=saga.saga_id,
                run_id=f"mixed-run-{ordinal}",
                delivery_status="completed",
            )
        )
        shadow_message_ids.append(snapshot.shadow_message_id)
    saga_store.record_anchor(
        saga_id=sagas[0].saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-a", im_message_id="existing-user-1"
        ),
    )

    asyncio.run(sync.recover_pending())

    assert [request["path"] for request in requests] == [
        f"/im/v1/conversations/shadow-a/external-agent-messages/{shadow_message_ids[0]}",
        "/im/v1/me",
        "/im/v1/nodes",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/shadow-a/messages",
        f"/im/v1/conversations/shadow-a/external-agent-messages/{shadow_message_ids[1]}",
    ]


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


def test_token_refresh_failure_happens_after_durable_saga_preparation(
    tmp_path: Path,
) -> None:
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")

    async def token_getter() -> str:
        raise httpx.ConnectError("auth endpoint unavailable")

    sync = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=token_getter,
        owner_user_id="owner-a",
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
                trigger_source="external",
            )
        ),
    )

    with pytest.raises(ShadowSyncPendingError):
        asyncio.run(sync.sync_user_message(inbound, agent_id="agent-a"))

    assert len(saga_store.pending()) == 1
    assert saga_store.pending()[0].provider_event_id == "event-a"


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


def test_terminal_task_keeps_captured_context_after_run_context_is_discarded(
    tmp_path: Path,
) -> None:
    """Detached completion cannot depend on the production runtime view staying live."""

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
    context_store = RunDeliveryContextStore()
    context_store.seed(
        RunDeliveryContext(
            run_id="run-1",
            agent_id="agent-a",
            kernel_session_id="session-1",
            delivery_target=RunDeliveryTarget.shadow(
                ShadowConversationRef(conversation_id="shadow-a")
            ),
            trigger_source="external",
            reply_channel_name="feishu:agent-a",
            reply_target_chat_id="chat-a",
            shadow_saga_id=saga.saga_id,
            message_id="im-agent-1",
            kernel_message_id="kernel-1",
            external_current_text="done",
        )
    )
    manager = Manager()
    reconciled: list[str] = []
    tracker = RuntimeDeliveryTaskTracker()

    async def reconcile(snapshot) -> None:
        reconciled.append(snapshot.shadow_message_id)

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=context_store,
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=reconcile,
        task_tracker=tracker,
    )

    async def emit() -> None:
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
        context_store.discard("run-1")
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit())

    assert manager.frames[-1]["kind"] == "message_completed"
    assert manager.frames[-1]["kernel_message_id"] == "kernel-1"
    assert reconciled


def test_offline_tool_state_is_closed_by_abnormal_terminal(tmp_path: Path) -> None:
    """Durable offline tools share the same in-flight lifecycle as live tools."""

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
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "trigger_source": "external",
                "reply_channel_name": "slack:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": saga.saga_id,
            }
        },
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
    )

    observer({"event": "run_status", "run_id": "run-1", "status": "running"})
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
            "event": "run_terminal_reconcile",
            "run_id": "run-1",
            "reason": "interrupted",
            "finalize_bubble": True,
            "delivery_status": "failed",
        }
    )

    snapshot = saga_store.pending_snapshots()[0]
    assert snapshot.tool_calls[0]["status"] == "failed"
    assert snapshot.tool_calls[0]["reason"] == "interrupted"


def test_online_abnormal_terminal_acks_then_reconciles_rich_snapshot(
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
    tracker = RuntimeDeliveryTaskTracker()

    async def reconcile(snapshot) -> None:
        reconciled.append(snapshot.shadow_message_id)

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "conversation_id": "shadow-a",
                "message_id": "im-agent-1",
                "trigger_source": "external",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": saga.saga_id,
                "kernel_message_id": "kernel-1",
                "external_current_text": "partial",
            }
        },
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=reconcile,
        task_tracker=tracker,
    )

    async def emit() -> None:
        pending = observer(
            {
                "event": "tool_start",
                "run_id": "run-1",
                "call_id": "call-1",
                "name": "read",
                "arguments": {"path": "a.py"},
            }
        )
        assert pending is not None
        await pending
        observer(
            {
                "event": "run_terminal_reconcile",
                "run_id": "run-1",
                "reason": "interrupted",
                "finalize_bubble": True,
                "delivery_status": "failed",
            }
        )
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit())

    assert [frame["kind"] for frame in manager.frames] == [
        "tool_call_upserted",
        "tool_call_completed",
        "message_completed",
    ]
    assert manager.frames[-1]["kernel_message_id"] == "kernel-1"
    assert manager.frames[-1]["elapsed_ms"] is not None
    assert reconciled


def test_failed_immediate_reconcile_notifies_recovery_owner(tmp_path: Path) -> None:
    class Manager:
        connected = True

        async def send_json(self, _message_type: str, _payload: dict[str, Any]) -> None:
            return None

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
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
    notifications: list[None] = []
    tracker = RuntimeDeliveryTaskTracker()

    async def fail_reconcile(_snapshot) -> None:
        raise httpx.ConnectError("IM temporarily unavailable")

    observer = build_kernel_event_observer(
        im_connection_manager_factory=Manager,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "conversation_id": "shadow-a",
                "message_id": "im-agent-1",
                "trigger_source": "external",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": saga.saga_id,
            }
        },
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=fail_reconcile,
        shadow_pending_notify=lambda: notifications.append(None),
        task_tracker=tracker,
    )

    async def emit() -> None:
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
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit())

    assert notifications
    assert saga_store.pending_snapshots()[0].state == "ready"


@pytest.mark.parametrize("failure_stage", ["roll", "reconcile"])
def test_failed_steer_bubble_reconcile_notifies_recovery_owner(
    tmp_path: Path, failure_stage: str
) -> None:
    class Manager:
        connected = True

        async def send_json(self, _message_type: str, _payload: dict[str, Any]) -> None:
            return None

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            if failure_stage == "roll" and payload["kind"] == "message_completed":
                raise RuntimeError("streaming roll rejected")
            if payload["kind"] == "turn_start":
                return {"payload": {"message_id": "im-agent-2"}}
            return {"payload": {"kind": payload["kind"]}}

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="steer-event"
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
    initial = saga_store.record(
        ExternalShadowBubbleEvent(kind="begin", saga_id=saga.saga_id, run_id="run-1")
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text", saga_id=saga.saga_id, run_id="run-1", content="before steer"
        )
    )
    notifications: list[None] = []

    async def fail_reconcile(_snapshot) -> None:
        if failure_stage == "reconcile":
            raise httpx.ConnectError("IM temporarily unavailable")

    context = {
        "run-1": {
            "agent_id": "agent-a",
            "conversation_id": "shadow-a",
            "message_id": "im-agent-1",
            "kernel_message_id": "kernel-a",
            "external_current_text": "before steer",
            "trigger_source": "external",
            "reply_channel_name": "feishu:agent-a",
            "reply_target_chat_id": "chat-a",
            "shadow_saga_id": saga.saga_id,
            "shadow_message_id": initial.shadow_message_id,
        }
    }
    manager = Manager()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=context,
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=fail_reconcile,
        shadow_pending_notify=lambda: notifications.append(None),
    )

    async def emit() -> None:
        pending = observer({"event": "injection_consumed", "run_id": "run-1"})
        assert pending is not None
        await pending
        next_shadow_message_id = context["run-1"]["shadow_message_id"]
        next_event = observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-b",
                "content": "after steer",
            }
        )
        assert next_event is not None
        await next_event
        assert context["run-1"]["shadow_message_id"] == next_shadow_message_id

    asyncio.run(emit())

    assert notifications == [None]
    assert saga_store.require_snapshot(initial.shadow_message_id).state == "ready"
    current = saga_store.require_snapshot(context["run-1"]["shadow_message_id"])
    assert current.state == "recording"
    assert current.content == "after steer"


def test_successful_steer_roll_does_not_reuse_the_previous_external_reply() -> None:
    class Manager:
        connected = True

        async def send_json(self, _message_type: str, _payload: dict[str, Any]) -> None:
            return None

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            if payload["kind"] == "turn_start":
                return {"payload": {"message_id": "im-agent-2"}}
            return {"payload": {"kind": payload["kind"]}}

    context = {
        "run-1": {
            "agent_id": "agent-a",
            "conversation_id": "shadow-a",
            "message_id": "im-agent-1",
            "kernel_message_id": "kernel-a",
            "external_current_text": "answer A",
            "external_intermediate_sent_marker": "kernel-a",
            "trigger_source": "external",
            "reply_channel_name": "feishu:agent-a",
            "reply_target_chat_id": "chat-a",
        }
    }
    mirrored: list[str] = []
    tracker = RuntimeDeliveryTaskTracker()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=Manager,
        run_context_store=context,
        external_reply_sender=lambda text, _metadata: mirrored.append(text),
        task_tracker=tracker,
    )

    async def emit() -> None:
        rolling = observer({"event": "injection_consumed", "run_id": "run-1"})
        assert rolling is not None
        await rolling
        assert context["run-1"]["message_id"] == "im-agent-2"
        assert "external_current_text" not in context["run-1"]
        assert "external_intermediate_sent_marker" not in context["run-1"]
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit())

    assert mirrored == []


def test_consumed_steer_moves_new_bubble_to_the_follower_saga(tmp_path: Path) -> None:
    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sagas = []
    for ordinal in (1, 2):
        inbound = attach_runtime_protocol(
            replace(
                _message(),
                external_event_identity=ExternalInboundEventIdentity(
                    connector_account_id="app-a",
                    provider_event_id=f"steer-saga-{ordinal}",
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
        saga = saga_store.prepare(
            message=inbound, agent_id="agent-a", owner_id="owner-a"
        )
        assert saga is not None
        sagas.append(saga)
    first = saga_store.record(
        ExternalShadowBubbleEvent(
            kind="begin", saga_id=sagas[0].saga_id, run_id="run-1"
        )
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text",
            saga_id=sagas[0].saga_id,
            run_id="run-1",
            content="answer A",
        )
    )
    context = {
        "run-1": {
            "agent_id": "agent-a",
            "conversation_id": "shadow-a",
            "message_id": "im-agent-1",
            "shadow_saga_id": sagas[0].saga_id,
            "shadow_message_id": first.shadow_message_id,
        }
    }
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: None,
        run_context_store=context,
        shadow_bubble_record=saga_store.record,
    )

    observer(
        {
            "event": "injection_consumed",
            "run_id": "run-1",
            "shadow_saga_id": sagas[1].saga_id,
        }
    )

    assert context["run-1"]["shadow_saga_id"] == sagas[1].saga_id
    new_shadow_message_id = context["run-1"]["shadow_message_id"]
    assert new_shadow_message_id != first.shadow_message_id
    snapshots = saga_store.pending_snapshots()
    assert snapshots[0].saga_id == sagas[0].saga_id
    assert (
        saga_store.require_snapshot(new_shadow_message_id).saga_id == sagas[1].saga_id
    )


def test_pending_follower_anchor_keeps_new_bubble_durable_until_recovery(
    tmp_path: Path,
) -> None:
    class Manager:
        connected = True

        def __init__(self) -> None:
            self.frames: list[dict[str, Any]] = []

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            self.frames.append(dict(payload))
            return {"payload": {"kind": payload["kind"]}}

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    sagas = []
    for ordinal in (1, 2):
        inbound = attach_runtime_protocol(
            replace(
                _message(),
                external_event_identity=ExternalInboundEventIdentity(
                    connector_account_id="app-a",
                    provider_event_id=f"pending-steer-{ordinal}",
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
        saga = saga_store.prepare(
            message=inbound, agent_id="agent-a", owner_id="owner-a"
        )
        assert saga is not None
        sagas.append(saga)
    saga_store.record_anchor(
        saga_id=sagas[0].saga_id,
        shadow_ref=ShadowConversationRef(
            conversation_id="shadow-a", im_message_id="im-user-1"
        ),
    )
    initial = saga_store.record(
        ExternalShadowBubbleEvent(
            kind="begin", saga_id=sagas[0].saga_id, run_id="run-1"
        )
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text",
            saga_id=sagas[0].saga_id,
            run_id="run-1",
            content="answer A",
            kernel_message_id="kernel-a",
        )
    )
    context = {
        "run-1": {
            "agent_id": "agent-a",
            "conversation_id": "shadow-a",
            "message_id": "im-agent-1",
            "kernel_message_id": "kernel-a",
            "external_current_text": "answer A",
            "shadow_saga_id": sagas[0].saga_id,
            "shadow_message_id": initial.shadow_message_id,
        }
    }
    manager = Manager()
    notifications: list[None] = []
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=context,
        shadow_bubble_record=saga_store.record,
        shadow_pending_notify=lambda: notifications.append(None),
    )

    async def emit() -> None:
        closing = observer(
            {
                "event": "injection_consumed",
                "run_id": "run-1",
                "shadow_saga_id": sagas[1].saga_id,
                "shadow_anchor_pending": True,
            }
        )
        assert closing is not None
        assert context["run-1"]["conversation_id"] == ""
        assert context["run-1"]["message_id"] == ""
        await closing
        assert (
            observer(
                {
                    "event": "assistant_message",
                    "run_id": "run-1",
                    "message_id": "kernel-b",
                    "content": "answer B",
                }
            )
            is None
        )
        assert (
            observer({"event": "turn_end", "run_id": "run-1", "completed": True})
            is None
        )

    asyncio.run(emit())

    assert notifications == [None, None]
    assert [frame["kind"] for frame in manager.frames] == ["message_completed"]
    saga_store.acknowledge(
        shadow_message_id=initial.shadow_message_id, im_message_id="im-agent-1"
    )
    current = saga_store.require_snapshot(context["run-1"]["shadow_message_id"])
    assert current.saga_id == sagas[1].saga_id
    assert current.state == "ready"
    assert current.content == "answer B"
    assert [saga.saga_id for saga in saga_store.recovery_sagas()] == [sagas[1].saga_id]


def test_failed_prior_bubble_reconcile_does_not_block_new_live_bubble(
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
                return {"payload": {"message_id": "im-agent-2"}}
            return {"payload": {"kind": payload["kind"]}}

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = attach_runtime_protocol(
        replace(
            _message(),
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="app-a", provider_event_id="multi-event"
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
    initial = saga_store.record(
        ExternalShadowBubbleEvent(kind="begin", saga_id=saga.saga_id, run_id="run-1")
    )
    saga_store.record(
        ExternalShadowBubbleEvent(
            kind="text",
            saga_id=saga.saga_id,
            run_id="run-1",
            content="answer A",
            kernel_message_id="kernel-a",
        )
    )
    manager = Manager()
    notifications: list[None] = []

    async def fail_reconcile(_snapshot) -> None:
        raise httpx.ConnectError("IM temporarily unavailable")

    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "conversation_id": "shadow-a",
                "message_id": "im-agent-1",
                "kernel_message_id": "kernel-a",
                "external_current_text": "answer A",
                "trigger_source": "external",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": saga.saga_id,
                "shadow_message_id": initial.shadow_message_id,
            }
        },
        external_reply_sender=lambda _text, _metadata: None,
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=fail_reconcile,
        shadow_pending_notify=lambda: notifications.append(None),
    )

    async def emit() -> None:
        pending = observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-b",
                "content": "answer B",
            }
        )
        assert pending is not None
        await pending

    asyncio.run(emit())

    assert notifications
    assert manager.frames[-1] == {
        "kind": "message_delta",
        "message_id": "im-agent-2",
        "delta_text": "answer B",
        "run_id": "run-1",
    }


def test_offline_terminal_releases_external_live_run_classification() -> None:
    class Manager:
        connected = False

        def __init__(self) -> None:
            self.finished: list[str] = []

        def finish_external_shadow_run(self, run_id: str) -> None:
            self.finished.append(run_id)

    manager = Manager()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store={
            "run-1": {
                "agent_id": "agent-a",
                "trigger_source": "external",
                "reply_channel_name": "feishu:agent-a",
                "reply_target_chat_id": "chat-a",
                "shadow_saga_id": "saga-1",
            }
        },
    )

    assert observer({"event": "turn_end", "run_id": "run-1", "completed": True}) is None
    assert manager.finished == ["run-1"]


def test_terminal_keeps_durable_text_when_next_live_turn_start_fails(
    tmp_path: Path,
) -> None:
    """Transport context from bubble A cannot overwrite durable bubble B."""

    class Manager:
        connected = True

        async def send_json(self, _message_type: str, _payload: dict[str, Any]) -> None:
            return None

        async def send_json_await_ack(
            self, _message_type: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            if payload["kind"] == "turn_start":
                raise RuntimeError("new bubble unavailable")
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
    tracker = RuntimeDeliveryTaskTracker()
    external_replies: list[str] = []
    context = {
        "run-1": {
            "agent_id": "agent-a",
            "conversation_id": "shadow-a",
            "message_id": "im-a",
            "trigger_source": "external",
            "reply_channel_name": "feishu:agent-a",
            "reply_target_chat_id": "chat-a",
            "shadow_saga_id": saga.saga_id,
            "kernel_message_id": "kernel-a",
            "external_current_text": "answer A",
        }
    }
    observer = build_kernel_event_observer(
        im_connection_manager_factory=Manager,
        run_context_store=context,
        external_reply_sender=lambda text, _metadata: external_replies.append(text),
        shadow_bubble_record=saga_store.record,
        shadow_bubble_reconcile=lambda _snapshot: asyncio.sleep(0),
        task_tracker=tracker,
    )

    async def emit() -> None:
        saga_store.record(
            ExternalShadowBubbleEvent(
                kind="begin", saga_id=saga.saga_id, run_id="run-1"
            )
        )
        saga_store.record(
            ExternalShadowBubbleEvent(
                kind="text",
                saga_id=saga.saga_id,
                run_id="run-1",
                content="answer A",
                kernel_message_id="kernel-a",
            )
        )
        pending = observer(
            {
                "event": "assistant_message",
                "run_id": "run-1",
                "message_id": "kernel-b",
                "content": "answer B",
            }
        )
        assert pending is not None
        await pending
        observer({"event": "turn_end", "run_id": "run-1", "completed": True})
        await tracker.close_and_drain(asyncio.get_running_loop().time() + 1)

    asyncio.run(emit())

    snapshots = saga_store.pending_snapshots()
    assert [snapshot.content for snapshot in snapshots] == ["answer A", "answer B"]
    assert snapshots[-1].kernel_message_id == "kernel-b"
    assert context["run-1"]["external_current_text"] == "answer B"
    assert context["run-1"]["message_id"] == ""
    assert external_replies == ["answer A"]


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
