"""Authenticated shadow-sync identity test."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.gateway.shadow_saga import ExternalShadowSagaStore
from personal_assistant.gateway.shadow_sync import (
    IMShadowConversationSync,
    ShadowSyncPendingError,
)


def test_external_shadow_sync_uses_authenticated_im_user_not_stale_config_user(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """External shadow writes use the Bearer-token user, not config.node.user_id."""
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = {}
        if request.content:
            payload = dict(json.loads(request.content.decode("utf-8")))
        requests.append({"path": request.url.path, "payload": payload})
        if request.url.path == "/im/v1/me":
            return httpx.Response(
                200,
                json={
                    "id": "actual-user",
                    "user_id": "actual-user",
                    "username": "nano",
                    "display_name": "Nano",
                    "owner_id": "actual-user",
                    "owned_node_ids": [],
                    "default_entry_node_id": None,
                    "locale": "en",
                    "created_at": "2026-07-02T00:00:00Z",
                },
            )
        if request.url.path == "/im/v1/nodes":
            return httpx.Response(
                200,
                json=[{"node_id": "node-a", "owner_id": "actual-user"}],
            )
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            assert payload["participant_ids"] == [
                "user:actual-user",
                "agent:agent-a",
            ]
            return httpx.Response(201, json={"id": "conv-shadow"})
        if request.url.path == "/im/v1/conversations/conv-shadow/messages":
            assert payload["sender_user_id"] == "actual-user"
            assert payload["suppress_relay"] is True
            return httpx.Response(201, json={"id": "msg-shadow"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    client = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=lambda: _async_value("token-1"),
        owner_user_id="stale-config-user",
        node_id="node-a",
        transport=httpx.MockTransport(handler),
        saga_store=saga_store,
    )
    inbound = _external_inbound()

    with caplog.at_level(logging.WARNING):
        shadow_ref = asyncio.run(client.sync_user_message(inbound, agent_id="agent-a"))
        replay_ref = asyncio.run(client.sync_user_message(inbound, agent_id="agent-a"))

    assert shadow_ref is not None
    assert replay_ref == shadow_ref
    assert shadow_ref.ref is not None
    assert shadow_ref.ref.conversation_id == "conv-shadow"
    assert shadow_ref.ref.im_message_id == "msg-shadow"
    assert shadow_ref.saga_id is not None
    assert saga_store.require(shadow_ref.saga_id).owner_id == "actual-user"
    assert saga_store.diagnostic_reasons() == (
        "shadow_owner_recovered:stale-config-user->actual-user",
    )
    assert "recovered stale configured owner" in caplog.text
    assert [item["path"] for item in requests] == [
        "/im/v1/me",
        "/im/v1/nodes",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/conv-shadow/messages",
    ]

    corrected_config_client = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=lambda: _async_value("token-1"),
        owner_user_id="actual-user",
        node_id="node-a",
        transport=httpx.MockTransport(handler),
        saga_store=saga_store,
    )
    corrected_replay = asyncio.run(
        corrected_config_client.sync_user_message(inbound, agent_id="agent-a")
    )

    assert corrected_replay == shadow_ref
    assert len(requests) == 4


def test_stale_owner_pending_saga_recovers_user_output_and_boundary(
    tmp_path: Path,
) -> None:
    """Recovery preserves one saga identity across its user, output, and boundary."""

    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "path": request.url.path,
                "idempotency_key": request.headers.get("Idempotency-Key"),
            }
        )
        if request.url.path == "/im/v1/me":
            return httpx.Response(200, json={"id": "actual-user"})
        if request.url.path == "/im/v1/nodes":
            return httpx.Response(
                200,
                json=[{"node_id": "node-a", "owner_id": "actual-user"}],
            )
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            return httpx.Response(201, json={"id": "conv-shadow"})
        if request.url.path == "/im/v1/conversations/conv-shadow/messages":
            message_id = f"msg-{len(requests)}"
            return httpx.Response(201, json={"id": message_id})
        raise AssertionError(f"unexpected request: {request.url.path}")

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    inbound = _external_inbound()
    stale_saga = saga_store.prepare(
        message=inbound,
        agent_id="agent-a",
        owner_id="stale-config-user",
    )
    assert stale_saga is not None
    pending_output = saga_store.prepare_output(
        saga_id=stale_saga.saga_id,
        run_id="run-1",
        output_kind="final",
        kernel_message_id="kernel-message-1",
        content="done",
    )
    promoted_saga_ids: list[str] = []
    client = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=lambda: _async_value("token-1"),
        owner_user_id="stale-config-user",
        node_id="node-a",
        transport=httpx.MockTransport(handler),
        saga_store=saga_store,
        promote_pending_boundary=lambda saga_id, _shadow_ref: promoted_saga_ids.append(
            saga_id
        ),
    )

    asyncio.run(client.recover_pending())
    asyncio.run(client.recover_pending())

    recovered = saga_store.require(stale_saga.saga_id)
    assert recovered.owner_id == "actual-user"
    assert recovered.shadow_ref is not None
    assert saga_store.pending() == ()
    assert saga_store.pending_outputs() == ()
    assert promoted_saga_ids == [stale_saga.saga_id]
    assert [request["path"] for request in requests] == [
        "/im/v1/me",
        "/im/v1/nodes",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/conv-shadow/messages",
        "/im/v1/conversations/conv-shadow/messages",
    ]
    assert requests[3]["idempotency_key"] == stale_saga.shadow_user_idempotency_key
    assert requests[4]["idempotency_key"] == pending_output.caller_idempotency_key


def test_cross_owner_token_cannot_reassign_pending_shadow_saga(tmp_path: Path) -> None:
    """A token rejected by the node owner gate cannot claim external history."""

    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/im/v1/me":
            return httpx.Response(
                200,
                json={"id": "bob-user", "owner_id": "bob-owner"},
            )
        if request.url.path == "/im/v1/nodes":
            return httpx.Response(
                200,
                json=[{"node_id": "alice-node", "owner_id": ""}],
            )
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            return httpx.Response(201, json={"id": "bob-shadow"})
        if request.url.path == "/im/v1/conversations/bob-shadow/messages":
            return httpx.Response(201, json={"id": "bob-message"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    saga_store = ExternalShadowSagaStore(db_path=tmp_path / "shadow-sagas.sqlite3")
    stale_saga = saga_store.prepare(
        message=_external_inbound(),
        agent_id="agent-a",
        owner_id="alice-user",
    )
    assert stale_saga is not None
    client = IMShadowConversationSync(
        base_url="http://im.local",
        token_getter=lambda: _async_value("bob-token"),
        owner_user_id="alice-user",
        node_id="alice-node",
        transport=httpx.MockTransport(handler),
        saga_store=saga_store,
    )

    with pytest.raises(ShadowSyncPendingError):
        asyncio.run(client.sync_user_message(_external_inbound(), agent_id="agent-a"))

    assert saga_store.require(stale_saga.saga_id).owner_id == "alice-user"
    assert saga_store.diagnostic_reasons() == ()
    assert requests == ["/im/v1/me", "/im/v1/nodes"]


def _external_inbound() -> InboundMessage:
    return InboundMessage(
        channel_name="feishu:agent-a",
        text="hello from lark",
        external_user_id="ou_user",
        external_chat_id="feishu:app:dm:ou_user",
        is_group=False,
        agent_id="agent-a",
        metadata={"sender_display_name": "你"},
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="feishu:app:dm:ou_user",
                agent_id="agent-a",
                conversation_type="direct",
                trigger_source="external",
            ),
            external_event=ExternalInboundEventIdentity(
                connector_account_id="app-a",
                provider_event_id="event-a",
            ),
        ),
    )


async def _async_value(value: str) -> str:
    return value
