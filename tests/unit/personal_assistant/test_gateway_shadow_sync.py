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
from personal_assistant.gateway.shadow_saga import ExternalShadowSagaStore
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

    assert shadow_ref == ShadowConversationRef(
        conversation_id="shadow-a", im_message_id="message-a"
    )
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


def test_legacy_external_metadata_remains_supported() -> None:
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

    assert shadow_ref == ShadowConversationRef(
        conversation_id="shadow-a", im_message_id="message-a"
    )
    create_payload = requests[1]["payload"]
    assert create_payload["external_source"] == "slack"
    assert create_payload["external_chat_id"] == "legacy-chat-id"
    assert create_payload["title"] == "agent-a · Legacy Team · slack"
