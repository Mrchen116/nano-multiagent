"""Global tool replies use the same image snapshots and private IM delivery as chat."""

import json
import sqlite3
import threading
from base64 import b64decode
from dataclasses import replace

import httpx
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
from personal_assistant.gateway.reply_images import ReplyImages
from tests.integration.test_global_gateway_runtime import (
    _Model,
    _close,
    _message,
    _receive,
    _runtime,
    _wait,
)


class _ImageModel(_Model):
    def __init__(self, text, *, pause=False):
        super().__init__(pause=pause)
        self.text = text

    async def generate(self, request):
        async for message in super().generate(request):
            calls = tuple(
                replace(call, arguments={**call.arguments, "text": self.text})
                if call.name == "send_message"
                else call
                for call in message.tool_calls
            )
            yield replace(message, tool_calls=calls)


def _images(tmp_path, monkeypatch, *, status=201):
    source = tmp_path / ".nanoassistant/exports/review-generated.png"
    source.parent.mkdir(parents=True)
    data = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    source.write_bytes(data)
    requests = []

    def upload(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/im/v1/conversations/c_group001/images"
        assert request.url.params["agent_id"] == "worker"
        assert request.headers["Authorization"] == "Bearer current-runtime-token"
        assert request.content == data
        return httpx.Response(
            status, json={"url": "/im/v1/conversations/c_group001/images/reply-image"}
        )

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(upload)),
    )
    images = ReplyImages(
        tmp_path / "images",
        im_base_url="http://im",
        token_getter=lambda: "current-runtime-token",
    )
    text = f"before ![generated](<{source}>) after"
    return images, source, text, requests


@pytest.mark.asyncio
@pytest.mark.parametrize("is_group", [False, True])
async def test_global_tool_reply_snapshots_and_uploads_native_image(
    tmp_path, monkeypatch, is_group
):
    images, source, text, requests = _images(tmp_path, monkeypatch)
    model = _ImageModel(text)
    rt = await _runtime(tmp_path, model, reply_images=images)
    try:
        await _receive(
            rt, replace(_message("request", "Show your image"), is_group=is_group)
        )
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert len(requests) == 1
        assert (
            rt.manager.sent[0]["text"]
            == "before ![generated](/im/v1/conversations/c_group001/images/reply-image) after"
        )
        with sqlite3.connect(images._db) as db:
            row = db.execute(
                "select owner_id,agent_id,manifest_json from reply_image_outputs"
            ).fetchone()
        assert row[:2] == ("owner", "worker")
        manifest = json.loads(row[2])
        assert (
            images.image_bytes(images.load(manifest["output_key"]).images[0])
            == source.read_bytes()
        )
        assert any(
            event["type"] == "dispatch_confirmed"
            for event in rt.store.read_unacked_events(limit=200)
        )
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_global_direct_image_retry_reuses_snapshot_and_upload_receipt(
    tmp_path, monkeypatch
):
    images, source, text, requests = _images(tmp_path, monkeypatch)
    model = _ImageModel(text)
    rt = await _runtime(tmp_path, model, reply_images=images)
    try:
        await _receive(
            rt, replace(_message("request", "Show your image"), is_group=False)
        )
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        original = dict(rt.manager.sent[0])
        source.unlink()
        result = await rt.handler.handle({**original, "text": text})
        assert result["ok"] is True
        assert len(requests) == 1
        assert rt.manager.sent[1] == original
        with sqlite3.connect(images._db) as db:
            assert (
                db.execute("select count(*) from reply_image_outputs").fetchone()[0]
                == 1
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
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_global_group_withheld_image_has_no_snapshot_until_new_input_is_read(
    tmp_path, monkeypatch
):
    images, _source, text, requests = _images(tmp_path, monkeypatch)
    model = _ImageModel(text, pause=True)
    rt = await _runtime(tmp_path, model, reply_images=images)
    try:
        await _receive(rt, _message("request", "Show your image"))
        await _wait(model.read_done.is_set)
        await _receive(rt, _message("correction", "Please revise first"))
        model.resume.set()
        await _wait(
            lambda: (
                rt.manager.sent
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert len(requests) == 1 and len(rt.manager.sent) == 1
        with sqlite3.connect(images._db) as db:
            keys = db.execute("select output_key from reply_image_outputs").fetchall()
        assert len(keys) == 1 and keys[0][0].endswith(":send-new")
        assert (
            len(
                [
                    event
                    for event in rt.store.read_unacked_events(limit=200)
                    if event["type"] == "draft_withheld"
                ]
            )
            == 1
        )
    finally:
        model.resume.set()
        await _close(rt)


@pytest.mark.asyncio
async def test_global_group_stale_commit_does_not_prepare_or_upload_image(
    tmp_path, monkeypatch
):
    images, _source, text, requests = _images(tmp_path, monkeypatch)
    model = _ImageModel(text)
    rt = await _runtime(tmp_path, model, reply_images=images)
    commits = []

    def stale(**kwargs):
        commits.append(kwargs)
        return "stale"

    monkeypatch.setattr(rt.kernel, "try_commit_output", stale)
    try:
        await _receive(rt, _message("request", "Show your image"))
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert len(commits) == 1 and commits[0]["draft"]["source"] == "send_message"
        assert not requests and not rt.manager.sent
        with sqlite3.connect(images._db) as db:
            assert (
                db.execute("select count(*) from reply_image_outputs").fetchone()[0]
                == 0
            )
        assert any(
            event["type"] == "draft_withheld"
            for event in rt.store.read_unacked_events(limit=200)
        )
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_global_image_upload_failure_keeps_text_without_exposing_source(
    tmp_path, monkeypatch
):
    images, source, text, requests = _images(tmp_path, monkeypatch, status=503)
    model = _ImageModel(text)
    rt = await _runtime(tmp_path, model, reply_images=images)
    try:
        await _receive(
            rt, replace(_message("request", "Show your image"), is_group=False)
        )
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        assert len(requests) == 1
        assert (
            rt.manager.sent[0]["text"] == "before （图片未能展示：图片上传失败） after"
        )
        assert str(source) not in rt.manager.sent[0]["text"]
    finally:
        await _close(rt)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_first", [False, True])
async def test_global_external_image_uses_provider_projection_and_saved_receipt(
    tmp_path, monkeypatch, fail_first
):
    images, source, text, requests = _images(tmp_path, monkeypatch)
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
    rt = await _runtime(
        tmp_path,
        model,
        reply_images=images,
        outbound_router=OutboundRouter(ChannelRegistry([channel])),
        image_account_id_provider=lambda name: channel.image_account_id,
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
            result = await rt.handler.handle({**rt.manager.sent[0], "text": text})
            assert result["ok"] is True
        assert len(requests) == 1
        assert client.uploads == [(data, "image/png")]
        assert len(client.sent) == 1
        assert client.sent[0]["text"] == "before ![generated](img_provider_saved) after"
        assert client.sent[0]["receive_id"] == "human"
        assert (
            rt.manager.sent[0]["text"]
            == "before ![generated](/im/v1/conversations/c_group001/images/reply-image) after"
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
            manifest["images"][0]["feishu_receipts"]["image-app:image-app"]["image_key"]
            == "img_provider_saved"
        )
    finally:
        client.release.set()
        await _close(rt)
