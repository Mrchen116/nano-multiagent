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


def _make_valid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Build a structurally complete PNG (IHDR + IDAT + IEND) with stdlib only.

    Used to guard against the structural check false-rejecting a real solid-color
    image (a valid image being killed is worse than a corrupt one slipping through).
    """
    import struct
    import zlib

    def _chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    idat = _chunk(b"IDAT", zlib.compress(raw, 9))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


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


def test_detected_mime_wins_over_client_content_type(tmp_path: Path) -> None:
    """bugfix-433-fix1 #6: magic-byte detected mime is trusted over client content_type.

    The attachment claims image/jpeg but the bytes are PNG; the data URL must carry the
    detected image/png (client-supplied content_type can be wrong / forged).
    """

    async def _png_fetcher(url: str) -> bytes:
        return _PNG_BYTES

    pipeline, kernel, _ = _make_pipeline(tmp_path, fetcher=_png_fetcher)
    inbound = InboundMessage(
        channel_name="web",
        text="what is this",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={
            "attachments": [
                {
                    "url": "http://im.local/im/uploads/a.png",
                    "content_type": "image/jpeg",  # lying content type
                }
            ]
        },
    )
    asyncio.run(pipeline.handle_inbound(inbound))

    url = kernel.send_calls[0]["image_urls"][0]["url"]
    assert url.startswith("data:image/png;base64,"), (
        f"detected png must win over claimed jpeg; got {url[:30]}"
    )


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


def test_corrupt_png_with_valid_magic_header_is_rejected(tmp_path: Path) -> None:
    """bugfix-433-fix1 Issue #1: a 41-byte PNG with a valid magic header but a corrupt
    body (no IHDR/IEND structure) must be rejected at inbound — NOT sent to the provider.

    Magic-byte detection alone passed this and let it reach Anthropic, which returned a
    stream error surfaced as '⚠️ 模型调用失败' instead of the fixed '无法识别' message.
    """
    # 8-byte PNG signature + 33 random ASCII bytes (not a valid IHDR chunk), 41 bytes total.
    corrupt_png = b"\x89PNG\r\n\x1a\n" + b"not a valid png body random ascii"
    assert len(corrupt_png) == 41

    async def _corrupt_fetcher(url: str) -> bytes:
        return corrupt_png

    pipeline, kernel, delivered = _make_pipeline(tmp_path, fetcher=_corrupt_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert kernel.send_calls == [], "corrupt PNG must not be submitted to the model"
    assert delivered == [
        "这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。"
    ]


def test_png_shorter_than_minimum_complete_length_is_rejected() -> None:
    """bugfix-433-fix3 #1: a PNG shorter than a complete one (45 bytes) is rejected even
    if it carries the IHDR + IEND markers — the old 28-byte threshold under-validated
    such short truncated payloads.

    Minimum complete PNG = signature(8) + IHDR chunk(25) + IEND chunk(12) = 45 bytes.
    """
    from personal_assistant.gateway.inbound_pipeline import _detect_image_mime

    # 44 bytes: valid signature, "IHDR" type at offset 12, contains "IEND" — but one
    # byte short of a complete PNG, so it must be rejected.
    short = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + b"x" * 24 + b"IEND"
    assert len(short) == 44
    assert _detect_image_mime(short) is None

    # 45-byte structurally complete PNG must pass (boundary just above the limit).
    valid = _make_valid_png(1, 1, (0, 0, 0))
    assert len(valid) >= 45
    assert _detect_image_mime(valid) == "image/png"


def test_valid_png_with_full_structure_passes(tmp_path: Path) -> None:
    """A structurally valid PNG (real IHDR + IEND) must still pass the strengthened check."""

    async def _ok_fetcher(url: str) -> bytes:
        return _PNG_BYTES

    pipeline, kernel, _ = _make_pipeline(tmp_path, fetcher=_ok_fetcher)
    asyncio.run(pipeline.handle_inbound(_image_inbound()))

    assert len(kernel.send_calls) == 1
    assert kernel.send_calls[0].get("image_urls"), "valid PNG must reach submit"


def test_real_multichunk_solid_color_png_not_false_rejected(tmp_path: Path) -> None:
    """bugfix-433-fix1: a real 100x100 solid-color PNG (IHDR+IDAT+IEND) must NOT be
    false-rejected by the structural check — false-killing a valid image is worse than
    missing a corrupt one (it silently breaks the core vision feature).
    """
    for idx, rgb in enumerate([(255, 0, 0), (0, 0, 255)]):  # red, blue
        png = _make_valid_png(100, 100, rgb)
        sub = tmp_path / f"case-{idx}"
        sub.mkdir()

        async def _fetcher(url: str, _png: bytes = png) -> bytes:
            return _png

        pipeline, kernel, delivered = _make_pipeline(sub, fetcher=_fetcher)
        asyncio.run(pipeline.handle_inbound(_image_inbound()))

        assert delivered == [], f"valid {rgb} PNG must not trigger a failure message"
        assert len(kernel.send_calls) == 1, f"valid {rgb} PNG must reach submit"
        url = kernel.send_calls[0]["image_urls"][0]["url"]
        assert url.startswith("data:image/png;base64,")


def test_corrupt_image_does_not_poison_following_text_turn(tmp_path: Path) -> None:
    """bugfix-433-fix1 Issue #2: after a corrupt image stops a turn, a following text
    message in the SAME session must submit normally (no poisoned history).

    Root cause: a submitted corrupt image persisted in history and was re-sent every
    later turn → repeated provider errors → empty replies. Rejecting the corrupt image
    at inbound (Issue #1) means it never enters history, so the session stays usable.
    """
    corrupt_png = b"\x89PNG\r\n\x1a\n" + b"not a valid png body random ascii"

    async def _corrupt_fetcher(url: str) -> bytes:
        return corrupt_png

    pipeline, kernel, delivered = _make_pipeline(tmp_path, fetcher=_corrupt_fetcher)

    # Turn 1: corrupt image → stopped, no submit.
    asyncio.run(pipeline.handle_inbound(_image_inbound()))
    assert kernel.send_calls == []

    # Turn 2: plain text in the same conversation → must submit normally.
    text_inbound = InboundMessage(
        channel_name="web",
        text="never mind, just text: what is 1+1?",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )
    asyncio.run(pipeline.handle_inbound(text_inbound))

    assert len(kernel.send_calls) == 1, (
        "following text turn must submit (session usable)"
    )
    assert kernel.send_calls[0]["texts"] == ["never mind, just text: what is 1+1?"]
    assert "image_urls" not in kernel.send_calls[0]


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
