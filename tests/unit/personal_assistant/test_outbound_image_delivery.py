"""Provider preparation receipts remain durable before public output admission."""

import asyncio
from pathlib import Path
from threading import Event

import pytest

from personal_assistant.channels.base import (
    OutboundImage,
    ProviderImageEntry,
    ProviderImagePreparation,
    ReplyContext,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.reply_images import ReplyImageContext, ReplyImages


class ImageChannel:
    name = "feishu"

    def __init__(self) -> None:
        self.uploads = 0
        self.receipts = []
        self.messages = []
        self.started = Event()
        self.release = Event()
        self.release.set()

    def prepare_images(self, outbound):
        self.uploads += 1
        self.started.set()
        assert self.release.wait(5)
        return "image-receipt"

    def send_prepared(self, outbound, preparation, *, before_publish, after_publish):
        assert self.receipts == [preparation]
        if not before_publish():
            return "suppressed"
        try:
            self.messages.append(outbound.text)
        finally:
            after_publish()
        return "delivered"


async def test_receipt_precedes_publication_and_suppression_does_not_claim_dedupe() -> (
    None
):
    channel = ImageChannel()
    router = OutboundRouter(ChannelRegistry((channel,)))
    reply = ReplyContext(
        "feishu", "chat", metadata={"reply_dedupe_key": "run:bubble:0"}
    )
    args = dict(
        text="![image](nano-image-pending:0)",
        reply_context=reply,
        images=(OutboundImage(0, b"image", "image/png", "a.png"),),
        record_provider_receipts=channel.receipts.append,
        after_publish=lambda: None,
    )
    result = await router.send_text_async(**args, before_publish=lambda: False)
    assert result is None
    assert channel.messages == []
    channel.receipts.clear()
    assert await router.send_text_async(**args, before_publish=lambda: True) is not None
    assert channel.messages == [args["text"]]


async def test_cancelled_upload_is_collected_and_saved_without_public_send() -> None:
    channel = ImageChannel()
    channel.release.clear()
    router = OutboundRouter(ChannelRegistry((channel,)))
    task = asyncio.create_task(
        router.send_text_async(
            text="![image](nano-image-pending:0)",
            reply_context=ReplyContext("feishu", "chat"),
            images=(OutboundImage(0, b"image", "image/png", "a.png"),),
            record_provider_receipts=channel.receipts.append,
            before_publish=lambda: True,
            after_publish=lambda: None,
        )
    )
    assert await asyncio.to_thread(channel.started.wait, 2)
    task.cancel()
    channel.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert channel.receipts == ["image-receipt"]
    assert channel.messages == []


async def test_failed_public_send_reuses_persisted_image_key_only_for_same_app(
    tmp_path: Path,
) -> None:
    """A reopened sender reuses acknowledged uploads without sharing Bot resources."""
    source = tmp_path / ".nanoassistant" / "exports" / "chart.png"
    source.parent.mkdir(parents=True)
    data = b"\x89PNG\r\n\x1a\nsnapshot"
    source.write_bytes(data)
    state_root = tmp_path / "images"
    context = ReplyImageContext("run:bubble:0", "owner", "agent", "run", "0", tmp_path)
    images = ReplyImages(state_root)
    prepared = images.prepare(context, f"Before ![chart]({source}) after")
    uploads: list[tuple[str, int]] = []
    published: list[str] = []

    class Provider:
        name = "feishu"

        def __init__(self, app_id: str, *, fail_send: bool = False) -> None:
            self.app_id = app_id
            self.fail_send = fail_send

        def prepare_images(self, outbound):
            entries = []
            for image in outbound.images:
                key = image.image_key
                if not key:
                    assert image.data == data
                    uploads.append((self.app_id, image.ordinal))
                    key = f"img_{self.app_id}_{image.ordinal}"
                entries.append(ProviderImageEntry(image.ordinal, key, None))
            return ProviderImagePreparation(self.app_id, self.app_id, tuple(entries))

        def send_prepared(
            self, outbound, preparation, *, before_publish, after_publish
        ):
            assert before_publish()
            try:
                # Public send may fail, but a different storage instance must
                # already observe every successful image-upload acknowledgement.
                reopened = ReplyImages(state_root)
                durable = reopened.load(context.output_key)
                assert durable is not None
                saved = reopened.outbound_images(durable, self.app_id)
                assert saved[0].image_key == preparation.entries[0].image_key
                if self.fail_send:
                    raise RuntimeError("public send failed")
                published.append(preparation.entries[0].image_key)
            finally:
                after_publish()
            return "delivered"

    async def send(store: ReplyImages, provider: Provider):
        router = OutboundRouter(ChannelRegistry((provider,)))
        return await router.send_text_async(
            text=prepared.markdown_template,
            reply_context=ReplyContext(
                "feishu", "chat", metadata={"reply_dedupe_key": context.output_key}
            ),
            images=store.outbound_images(prepared, provider.app_id),
            record_provider_receipts=lambda receipts: store.record_provider_receipts(
                context.output_key, receipts
            ),
            before_publish=lambda: True,
            after_publish=lambda: None,
        )

    with pytest.raises(RuntimeError, match="public send failed"):
        await send(images, Provider("app-a", fail_send=True))
    assert uploads == [("app-a", 0)]
    assert published == []

    source.unlink()
    restarted = ReplyImages(state_root)
    assert await send(restarted, Provider("app-a")) is not None
    assert uploads == [("app-a", 0)]
    assert published == ["img_app-a_0"]

    assert await send(ReplyImages(state_root), Provider("app-b")) is not None
    assert uploads == [("app-a", 0), ("app-b", 0)]
    assert published == ["img_app-a_0", "img_app-b_0"]
