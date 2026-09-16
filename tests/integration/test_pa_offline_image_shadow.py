"""Offline IM must not prevent the originating provider's prepared image reply."""

import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundIngress,
    ProviderImageEntry,
    ProviderImagePreparation,
)
from personal_assistant.gateway.inbound_models import ShadowConversationRef
from tests.integration.test_pa_candidate_delivery import build, close
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


class Feishu:
    name = "feishu"
    image_account_id = "app-test"

    def __init__(self, source):
        self.prepared = []
        self.sent = []
        self.source = source

    def prepare_images(self, outbound):
        self.prepared.append(outbound)
        return ProviderImagePreparation(
            "app-test",
            "app-test",
            tuple(
                ProviderImageEntry(i.ordinal, f"key-{i.ordinal}")
                for i in outbound.images
            ),
        )

    def send_prepared(self, outbound, preparation, *, before_publish, after_publish):
        assert before_publish()
        self.sent.append((outbound, preparation))
        self.source.unlink(missing_ok=True)
        after_publish()
        return "delivered"

    def send(self, outbound):
        self.sent.append((outbound, None))


@pytest.mark.asyncio
@pytest.mark.parametrize("has_anchor", [True, False])
async def test_offline_feishu_image_delivers_then_shadow_reuses_snapshot_after_source_removal(
    tmp_path, monkeypatch, has_anchor
):
    source = tmp_path / "feishu.png"
    data = b"\x89PNG\r\n\x1a\nfeishu-original"
    source.write_bytes(data)
    online = False
    reconciled = []

    def http_response(request):
        if not online:
            raise httpx.ConnectError("IM offline", request=request)
        if request.url.path == "/im/v1/me":
            return httpx.Response(200, json={"id": "u_owner"})
        if request.url.path == "/im/v1/nodes":
            return httpx.Response(
                200, json=[{"node_id": "node-m248", "owner_id": "u_owner"}]
            )
        if request.url.path.endswith("/external/find-or-create"):
            return httpx.Response(200, json={"id": "c_chat"})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"id": "shadow-user"})
        if "/external-agent-messages/" in request.url.path:
            reconciled.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "shadow-ack"})
        return None

    rt, model, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [f"Here ![photo](<{source}>)"],
        http_handler=http_response,
    )
    adapter = Feishu(source)
    rt._channel_registry.register(adapter)
    rt._im_connection_manager.connected = False
    sync = rt._on_inbound._pipeline._shadow_sync
    message = replace(
        inbound(chat_id="oc_feishu", text="send image"),
        channel_name="feishu",
        ingress=InboundIngress(
            external_conversation=ExternalConversationIdentity(
                "feishu",
                "oc_feishu",
                agent_id="agent-a",
                conversation_type="direct",
                trigger_source="feishu",
            ),
            external_event=ExternalInboundEventIdentity("app-test", "event-one"),
        ),
    )
    saga = sync._saga_store.prepare(
        message=message, agent_id="agent-a", owner_id="u_owner"
    )
    if has_anchor:
        sync._saga_store.record_anchor(
            saga_id=saga.saga_id,
            shadow_ref=ShadowConversationRef("c_chat", "shadow-user"),
        )
    try:
        result = await asyncio.wait_for(
            rt._on_inbound._pipeline.handle_inbound(message), 10
        )
        await rt._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
        assert result.run_id
        assert len(model.requests) == 1
        assert len(model.permission_requests) == 1
        assert len(adapter.sent) == 1
        assert adapter.sent[0][1] is not None
        assert adapter.prepared[0].images[0].data == data
        assert not source.exists()
        assert not uploads
        pending = sync._saga_store.pending_snapshots()
        assert pending
        canonical = rt._startup_collaborators[0].images.load(pending[0].output_key)
        assert canonical is not None
        assert (
            rt._startup_collaborators[0].images.image_bytes(canonical.images[0]) == data
        )
        online = True
        rt._im_connection_manager.connected = True
        await sync.recover_pending()
        assert len(uploads) == 1
        assert reconciled
        assert reconciled[-1]["delivery_status"] == "completed"
        assert "http://im.test/im/v1/images/image123" in reconciled[-1]["content"]
        assert str(source) not in reconciled[-1]["content"]
        assert len(adapter.sent) == 1
    finally:
        await close(rt)
