"""Shadow identity checks and machine writes use separate credentials."""

from tests.helpers.message_delivery import shadow_sync_with_delivery

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


@pytest.mark.asyncio
async def test_shadow_recovery_retains_owner_checks_and_uses_rotated_runtime_token(
    tmp_path,
):
    runtime_token = None
    seen = []

    async def owner():
        return "owner-jwt"

    async def runtime():
        return runtime_token

    def respond(request):
        seen.append(request)
        if request.url.path in {"/im/v1/me", "/im/v1/nodes"}:
            assert request.headers["Authorization"] == "Bearer owner-jwt"
            payload = (
                {"id": "real-owner"}
                if request.url.path.endswith("/me")
                else [{"node_id": "node", "owner_id": "real-owner"}]
            )
            return httpx.Response(200, json=payload)
        assert request.headers["Authorization"] == f"Bearer {runtime_token}"
        assert runtime_token is not None
        if request.url.path.endswith("find-or-create"):
            return httpx.Response(201, json={"id": "shadow"})
        assert request.url.params["agent_id"] == "agent"
        return httpx.Response(201, json={"id": "message"})

    store = ExternalShadowSagaStore(db_path=tmp_path / "sagas.sqlite")
    sync = shadow_sync_with_delivery(
        base_url="http://im.local",
        token_getter=owner,
        gateway_token_getter=runtime,
        owner_user_id="stale-config-owner",
        node_id="node",
        saga_store=store,
        transport=httpx.MockTransport(respond),
    )
    message = InboundMessage(
        channel_name="feishu:agent",
        text="hello",
        external_user_id="external-human",
        external_chat_id="group",
        is_group=True,
        agent_id="agent",
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id="group",
                agent_id="agent",
                conversation_type="group",
                trigger_source="external",
            ),
            external_event=ExternalInboundEventIdentity(
                connector_account_id="app", provider_event_id="event"
            ),
        ),
    )
    with pytest.raises(ShadowSyncPendingError) as pending:
        await sync.sync_user_message(message, agent_id="agent")
    assert store.require(pending.value.saga_id).shadow_ref is None
    assert all(request.url.path in {"/im/v1/me", "/im/v1/nodes"} for request in seen)
    runtime_token = "runtime-one"
    recovered = await sync.sync_user_message(message, agent_id="agent")
    assert recovered.ref.conversation_id == "shadow"
    assert store.require(recovered.saga_id).owner_id == "real-owner"
    runtime_token = "runtime-two"
    await sync.mirror_agent_output(
        saga_id=recovered.saga_id,
        run_id="run",
        output_kind="final",
        kernel_message_id="k1",
        content="answer",
    )
    assert seen[-1].headers["Authorization"] == "Bearer runtime-two"
    runtime_token = None
    with pytest.raises(ConnectionError):
        await sync.mirror_agent_output(
            saga_id=recovered.saga_id,
            run_id="run",
            output_kind="intermediate",
            kernel_message_id="k2",
            content="later",
        )
    assert len(store.pending_outputs()) == 1
    assert sum(request.url.path == "/im/v1/me" for request in seen) == 1
