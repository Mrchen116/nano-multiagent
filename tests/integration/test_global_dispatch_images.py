"""Global tool replies use the same image snapshots and private IM delivery as chat."""

import json
import sqlite3
from base64 import b64decode
from dataclasses import replace

import httpx
import pytest

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
        if request.url.path == "/im/v1/image-delivery/target":
            return httpx.Response(200, json={"conversation_id": "c_group001"})
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
        assert rt.manager.sent == [original]
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
@pytest.mark.parametrize("mixed", [False, True])
async def test_global_reply_preserves_current_chat_image_reference_on_retry(
    tmp_path, monkeypatch, mixed
):
    images, source, local_text, requests = _images(tmp_path, monkeypatch)
    known = "/im/v1/conversations/c_group001/images/" + "a" * 32
    text = f"Reusing ![earlier image]({known})"
    if mixed:
        text += " and " + local_text
    model = _ImageModel(text)
    rt = await _runtime(tmp_path, model, reply_images=images)
    try:
        await _receive(
            rt,
            replace(
                _message("request", f"Please show this again: ![image]({known})"),
                is_group=False,
            ),
        )
        await _wait(
            lambda: (
                model.requests
                and not rt.coordinator._monitors
                and not rt.coordinator._drains
            )
        )
        expected = f"Reusing ![earlier image]({known})"
        if mixed:
            expected += " and before ![generated](/im/v1/conversations/c_group001/images/reply-image) after"
        assert rt.manager.sent[0]["text"] == expected
        source.unlink()
        result = await rt.handler.handle({**rt.manager.sent[0], "text": text})
        assert result["ok"] is True
        assert len(rt.manager.sent) == 1
        assert len(requests) == int(mixed)
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
async def test_global_group_stale_commit_does_not_publish_prepared_image(
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
        assert len(requests) == 1 and not rt.manager.sent
        with sqlite3.connect(images._db) as db:
            assert (
                db.execute("select count(*) from reply_image_outputs").fetchone()[0]
                == 1
            )
        assert any(
            event["type"] == "draft_withheld"
            for event in rt.store.read_unacked_events(limit=200)
        )
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_global_image_upload_failure_withholds_entire_text(tmp_path, monkeypatch):
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
        assert not rt.manager.sent
    finally:
        await _close(rt)


@pytest.mark.asyncio
async def test_explicit_user_image_target_is_resolved_before_reading(
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
        original = rt.manager.sent[0]
        result = await rt.handler.handle(
            {
                **original,
                "dispatch_request_id": "user-image",
                "to": "u_target01",
                "text": text,
            }
        )
        assert result["ok"] is True
        assert rt.manager.sent[-1]["to"] == "u_target01"
        assert "/im/v1/conversations/c_group001/images/" in rt.manager.sent[-1]["text"]
        assert len(requests) == 2
    finally:
        await _close(rt)
