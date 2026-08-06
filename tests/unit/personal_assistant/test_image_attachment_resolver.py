"""Public behavior tests for Gateway image attachment resolution."""

from __future__ import annotations

import base64

import pytest

from personal_assistant.gateway.image_attachments import ImageAttachmentResolver


_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _attachments(*, content_type: str = "image/jpeg") -> list[dict[str, str]]:
    return [
        {
            "url": "http://im.local/im/uploads/a.png",
            "content_type": content_type,
        }
    ]


@pytest.mark.asyncio
async def test_resolve_returns_typed_data_url_with_detected_mime() -> None:
    """Downloaded bytes become typed parts and detected MIME overrides client input."""

    async def _fetch(url: str) -> bytes:
        assert url.endswith("/a.png")
        return _PNG_BYTES

    result = await ImageAttachmentResolver(fetcher=_fetch).resolve(_attachments())

    assert result.failure is None
    assert len(result.parts) == 1
    assert result.parts[0]["mime_type"] == "image/png"
    assert result.parts[0]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_resolve_accepts_self_contained_data_url_without_http_fetch() -> None:
    async def _fetch(_url: str) -> bytes:
        raise AssertionError("data URLs must not be sent to the IM HTTP fetcher")

    data_url = "data:image/png;base64," + base64.b64encode(_PNG_BYTES).decode()

    result = await ImageAttachmentResolver(fetcher=_fetch).resolve(
        [{"url": data_url, "content_type": "image/png"}]
    )

    assert result.failure is None
    assert result.parts == (
        {"type": "image", "image_url": data_url, "mime_type": "image/png"},
    )


@pytest.mark.asyncio
async def test_resolve_without_fetcher_preserves_raw_url() -> None:
    """Product-agnostic wiring keeps the original URL and supplied MIME."""

    result = await ImageAttachmentResolver().resolve(
        _attachments(content_type="image/png")
    )

    assert result.failure is None
    assert result.parts == (
        {
            "type": "image",
            "image_url": "http://im.local/im/uploads/a.png",
            "mime_type": "image/png",
        },
    )


@pytest.mark.asyncio
async def test_resolve_without_fetcher_still_validates_self_contained_data_url() -> (
    None
):
    result = await ImageAttachmentResolver(max_image_bytes=8).resolve(
        [{"url": "data:image/png;base64," + base64.b64encode(_PNG_BYTES).decode()}]
    )

    assert result.parts == ()
    assert result.failure == "oversize"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "max_bytes", "expected_failure"),
    [
        (b"", 1024, "download"),
        (_PNG_BYTES, 8, "oversize"),
        (b"not an image", 1024, "corrupt"),
        (b"\x89PNG\r\n\x1a\n" + b"x" * 36, 1024, "corrupt"),
    ],
)
async def test_resolve_returns_typed_failure_for_invalid_image(
    payload: bytes,
    max_bytes: int,
    expected_failure: str,
) -> None:
    """The first invalid attachment fails the whole resolution without partial parts."""

    async def _fetch(_url: str) -> bytes:
        return payload

    result = await ImageAttachmentResolver(
        fetcher=_fetch,
        max_image_bytes=max_bytes,
    ).resolve(_attachments())

    assert result.parts == ()
    assert result.failure == expected_failure


@pytest.mark.asyncio
async def test_resolve_maps_fetch_exception_to_download_failure() -> None:
    """Fetcher errors are exposed as the stable download failure kind."""

    async def _fetch(_url: str) -> bytes:
        raise RuntimeError("unavailable")

    result = await ImageAttachmentResolver(fetcher=_fetch).resolve(_attachments())

    assert result.parts == ()
    assert result.failure == "download"
