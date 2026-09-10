"""Provider preparation receipts remain durable before public output admission."""

import asyncio
from threading import Event

import pytest

from personal_assistant.channels.base import OutboundImage, ReplyContext
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter


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
