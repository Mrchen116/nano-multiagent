"""Explicit global image replies retain provider receipts and channel boundaries."""

import json
import sqlite3
import threading
from dataclasses import replace

import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    InboundIngress,
)
from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_models import (
    GatewayShadowState,
    ShadowConversationRef,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from tests.integration.test_global_dispatch_images import _ImageModel, _images
from tests.integration.test_global_gateway_runtime import (
    _close,
    _message,
    _runtime,
    _wait,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_first", [False, True])
@pytest.mark.parametrize("include_hosted", [False, True])
async def test_global_external_image_uses_provider_projection_and_saved_receipt(
    tmp_path, monkeypatch, fail_first, include_hosted
):
    images, source, text, requests = _images(tmp_path, monkeypatch)
    hosted_prefix = ""
    if include_hosted:
        known = "/im/v1/conversations/c_group001/images/" + "a" * 32
        hosted_prefix = f"![earlier image]({known}) "
        text = hosted_prefix + text
    data = source.read_bytes()

    class Client:
        def __init__(self):
            self.uploads = []
            self.sent = []
            self.started = threading.Event()
            self.release = threading.Event()
            self.fail = fail_first

        def upload_image(self, content, *, content_type):
            self.uploads.append((content, content_type))
            return "img_provider_saved"

        def send_prepared_message(self, **kwargs):
            self.started.set()
            self.release.wait(timeout=10)
            assert kwargs["before_publish"]()
            if self.fail:
                raise RuntimeError("provider rejected delivery")
            self.sent.append(kwargs)
            return "delivered"

    client = Client()
    channel = FeishuAdapter(
        name="feishu:worker",
        app_id="image-app",
        app_secret="test-secret",
        group_context_store=GroupContextStore(tmp_path / "groups.sqlite3"),
    )
    channel._client = client
    model = _ImageModel(text)
    registry = ChannelRegistry([channel])
    rt = await _runtime(
        tmp_path,
        model,
        reply_images=images,
        outbound_router=OutboundRouter(registry),
        channel_registry=registry,
    )
    try:
        message = replace(
            _message("provider-m1", "Show your image"),
            channel_name=channel.name,
            external_chat_id="feishu:image-app:dm:human",
            is_group=False,
            ingress=InboundIngress(
                external_event=ExternalInboundEventIdentity("image-app", "provider-m1"),
                external_conversation=ExternalConversationIdentity(
                    "feishu",
                    "feishu:image-app:dm:human",
                    "worker",
                    "direct",
                    "external",
                ),
            ),
        )
        await rt.coordinator.receive(
            message=message,
            agent=rt.catalog.require("worker"),
            shadow=GatewayShadowState(
                saga_id="saga-m1", ref=ShadowConversationRef("c_group001", "shadow-m1")
            ),
            should_process=True,
            sender_label="Human",
        )
        if include_hosted:
            await _wait(
                lambda: (
                    model.requests
                    and not rt.coordinator._monitors
                    and not rt.coordinator._drains
                )
            )
            assert not rt.manager.sent
            assert not client.sent
            return
        await _wait(client.started.is_set)
        assert not any(
            event["type"] == "dispatch_confirmed"
            for event in rt.store.read_unacked_events(limit=200)
        )
        source.unlink()
        client.release.set()
        await _wait(lambda: not rt.coordinator._monitors and not rt.coordinator._drains)
        if fail_first:
            assert not client.sent
            assert not any(
                event["type"] == "dispatch_confirmed"
                for event in rt.store.read_unacked_events(limit=200)
            )
            client.fail = False
            result = await rt.handler.handle(
                {
                    **rt.manager.sent[0],
                    "text": text,
                    "dispatch_request_id": "model-fresh-call",
                }
            )
            assert result["ok"] is True
            assert len(rt.manager.sent) == 1
            assert client.sent[0]["idempotency_key"].endswith(":send-first")
        assert len(requests) == 1
        assert client.uploads == [(data, "image/png")]
        assert len(client.sent) == 1
        provider_prefix = "图片未能展示：图片快照不可用 " if include_hosted else ""
        assert (
            client.sent[0]["text"]
            == provider_prefix + "before ![generated](img_provider_saved) after"
        )
        assert "/im/v1/" not in client.sent[0]["text"]
        assert client.sent[0]["receive_id"] == "human"
        assert (
            rt.manager.sent[0]["text"]
            == hosted_prefix
            + "before ![generated](/im/v1/conversations/c_group001/images/reply-image) after"
        )
        assert (
            len(
                [
                    event
                    for event in rt.store.read_unacked_events(limit=200)
                    if event["type"] == "dispatch_confirmed"
                ]
            )
            == 1
        )
        with sqlite3.connect(images._db) as db:
            manifest = json.loads(
                db.execute("select manifest_json from reply_image_outputs").fetchone()[
                    0
                ]
            )
        assert (
            manifest["images"][-1]["feishu_receipts"]["image-app:image-app"][
                "image_key"
            ]
            == "img_provider_saved"
        )
    finally:
        client.release.set()
        await _close(rt)
