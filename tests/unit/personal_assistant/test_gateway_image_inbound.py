"""Gateway image attachment wiring and user-visible failure behavior."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore
from tests.helpers.inbound_pipeline import build_inbound_pipeline

from ._pipeline_helpers import _FakeChannel, _FakeKernel, _agents


_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _make_pipeline(tmp_path: Path, *, fetcher=None):
    channel = _FakeChannel("web")
    kernel = _FakeKernel()
    delivered: list[str] = []

    async def _bg_sender(text, reply_context, from_session_id):  # noqa: ANN001
        del reply_context, from_session_id
        delivered.append(text)

    pipeline = build_inbound_pipeline(
        kernel=kernel,
        agents=_agents(tmp_path),
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
        image_resolver=ImageAttachmentResolver(fetcher=fetcher),
        bg_reply_sender=_bg_sender,
    )
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


def test_inbound_downloads_attachment_before_kernel_submit(tmp_path: Path) -> None:
    """The pipeline connects resolver output to the Kernel image part."""

    async def _fetcher(url: str) -> bytes:
        assert url == "http://im.local/im/uploads/a.png"
        return _PNG_BYTES

    pipeline, kernel, _ = _make_pipeline(tmp_path, fetcher=_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert len(kernel.send_calls) == 1
    image_urls = kernel.send_calls[0]["image_urls"]
    assert image_urls[0]["url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize(
    ("failure", "expected_message"),
    [
        (
            "download",
            "这张图片没能加载，我没有收到它，无法据此回复。请重新发送图片试试。",
        ),
        (
            "oversize",
            "这张图片太大了，超出可接收的大小，我没能收到它，"
            "无法据此回复。请压缩或换一张更小的图片后重新发送。",
        ),
        (
            "corrupt",
            "这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。",
        ),
    ],
)
def test_image_failure_stops_submit_and_replies_with_actionable_message(
    tmp_path: Path,
    failure: str,
    expected_message: str,
) -> None:
    async def _fetcher(_url: str) -> bytes:
        if failure == "download":
            raise RuntimeError("404 not found")
        if failure == "oversize":
            return b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)
        return b"this is not an image"

    pipeline, kernel, delivered = _make_pipeline(tmp_path, fetcher=_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert kernel.send_calls == []
    assert delivered == [expected_message]


def test_corrupt_image_does_not_poison_following_text_turn(tmp_path: Path) -> None:
    """Rejecting corrupt bytes leaves the same conversation usable next turn."""

    async def _fetcher(_url: str) -> bytes:
        return b"\x89PNG\r\n\x1a\n" + b"not a valid png body random ascii"

    pipeline, kernel, _ = _make_pipeline(tmp_path, fetcher=_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))
    assert kernel.send_calls == []

    asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="never mind, just text: what is 1+1?",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
            )
        )
    )

    assert len(kernel.send_calls) == 1
    assert kernel.send_calls[0]["texts"] == ["never mind, just text: what is 1+1?"]
    assert "image_urls" not in kernel.send_calls[0]
