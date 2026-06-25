"""bugfix-433 决策1/5: gateway inbound downloads IM image attachments to base64 data
URLs, and on download/size/parse failure stops the turn (no submit) and replies with a
fixed user-facing message via the outbound sender — never feeding a placeholder to the model.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeKernel, _FakeChannel, _agents


# 1x1 PNG (valid magic bytes).
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _make_pipeline(tmp_path: Path, *, fetcher=None):
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        attachment_fetcher=fetcher,
    )
    delivered: list[str] = []

    async def _bg_sender(text, reply_context, from_session_id):
        delivered.append(text)

    pipeline._bg_reply_sender = _bg_sender
    return pipeline, kernel, delivered


def _image_inbound() -> InboundMessage:
    return InboundMessage(
        channel_name="web",
        text="what is this",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={
            "attachments": [
                {
                    "url": "http://im.local/im/uploads/a.png",
                    "content_type": "image/png",
                }
            ]
        },
    )


def test_inbound_downloads_attachment_to_base64_data_url(tmp_path: Path) -> None:
    """Successful download → image part submitted as a base64 data URL (not the HTTP URL)."""

    async def _ok_fetcher(url: str) -> bytes:
        assert url == "http://im.local/im/uploads/a.png"
        return _PNG_BYTES

    pipeline, kernel, _ = _make_pipeline(tmp_path, fetcher=_ok_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert len(kernel.send_calls) == 1
    image_urls = kernel.send_calls[0].get("image_urls")
    assert image_urls, "image part must reach submit"
    url = image_urls[0]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64encode(_PNG_BYTES).decode() in url


def test_download_failure_stops_turn_with_fixed_message(tmp_path: Path) -> None:
    """Download failure → no submit, fixed '没能加载' reply via outbound."""

    async def _fail_fetcher(url: str) -> bytes:
        raise RuntimeError("404 not found")

    pipeline, kernel, delivered = _make_pipeline(tmp_path, fetcher=_fail_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert kernel.send_calls == [], "must not submit on download failure"
    assert delivered == [
        "这张图片没能加载，我没有收到它，无法据此回复。请重新发送图片试试。"
    ]


def test_oversize_image_stops_turn_with_fixed_message(tmp_path: Path) -> None:
    """Image over the size limit → no submit, fixed '太大了' reply via outbound."""

    big = b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)

    async def _big_fetcher(url: str) -> bytes:
        return big

    pipeline, kernel, delivered = _make_pipeline(tmp_path, fetcher=_big_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert kernel.send_calls == []
    assert delivered == [
        "这张图片太大了，超出可接收的大小，我没能收到它，"
        "无法据此回复。请压缩或换一张更小的图片后重新发送。"
    ]


def test_corrupt_image_stops_turn_with_fixed_message(tmp_path: Path) -> None:
    """Unrecognizable image bytes → no submit, fixed '无法识别' reply via outbound."""

    async def _garbage_fetcher(url: str) -> bytes:
        return b"this is not an image"

    pipeline, kernel, delivered = _make_pipeline(tmp_path, fetcher=_garbage_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert kernel.send_calls == []
    assert delivered == [
        "这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。"
    ]


def test_no_fetcher_configured_keeps_http_url(tmp_path: Path) -> None:
    """Product-agnostic default (no fetcher): attachment passes through unchanged.

    The kernel/mapper only delivers data URLs, so an un-fetched HTTP URL won't reach a
    provider — but the pipeline stays IM-agnostic for unit/test wiring without a fetcher.
    """
    pipeline, kernel, _ = _make_pipeline(tmp_path, fetcher=None)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert len(kernel.send_calls) == 1
    image_urls = kernel.send_calls[0].get("image_urls")
    assert image_urls[0]["url"] == "http://im.local/im/uploads/a.png"
