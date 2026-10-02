"""Public behavior tests for Gateway image attachment resolution."""

from __future__ import annotations

import base64

import pytest

from personal_assistant.gateway.image_attachments import ImageAttachmentResolver


_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAgAAAQABAAD//gAQTGF2YzYxLjE5LjEwMQD/2wBDAAgEBAQEBAUFBQUFBQYGBgYGBgYGBgYGBgYGBgYHBwcICAgHBwcGBgcHCAgICAkJCQgICAgJCQoKCgwMCwsODg4RERT/xABMAAEBAAAAAAAAAAAAAAAAAAAABgEBAQAAAAAAAAAAAAAAAAAABgcQAQAAAAAAAAAAAAAAAAAAAAARAQAAAAAAAAAAAAAAAAAAAAD/wAARCAACAAIDASIAAhEAAxEA/9oADAMBAAIRAxEAPwCLAFF/f//Z"
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

    async def _fetch(url: str, agent_id: str) -> bytes:
        assert url.endswith("/a.png")
        return _PNG_BYTES

    result = await ImageAttachmentResolver(fetcher=_fetch).resolve(_attachments())

    assert result.failure is None
    assert len(result.parts) == 1
    assert result.parts[0]["mime_type"] == "image/png"
    assert result.parts[0]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_resolve_accepts_complete_jpeg_with_trailing_data() -> None:
    """A complete JPEG remains valid when metadata follows its EOI marker."""

    async def _fetch(_url: str, agent_id: str) -> bytes:
        return _JPEG_BYTES + b"synthetic-trailing-data"

    result = await ImageAttachmentResolver(fetcher=_fetch).resolve(_attachments())

    assert result.failure is None
    assert result.parts[0]["mime_type"] == "image/jpeg"
    assert result.parts[0]["image_url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_resolve_accepts_self_contained_data_url_without_http_fetch() -> None:
    async def _fetch(_url: str, agent_id: str) -> bytes:
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
async def test_resolve_without_fetcher_rejects_untrusted_raw_url() -> None:
    result = await ImageAttachmentResolver().resolve(
        _attachments(content_type="image/png")
    )
    assert result.failure == "download"
    assert result.parts == ()


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
        (_JPEG_BYTES.removesuffix(b"\xff\xd9"), 1024, "corrupt"),
    ],
)
async def test_resolve_returns_typed_failure_for_invalid_image(
    payload: bytes,
    max_bytes: int,
    expected_failure: str,
) -> None:
    """The first invalid attachment fails the whole resolution without partial parts."""

    async def _fetch(_url: str, agent_id: str) -> bytes:
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

    async def _fetch(_url: str, agent_id: str) -> bytes:
        raise RuntimeError("unavailable")

    result = await ImageAttachmentResolver(fetcher=_fetch).resolve(_attachments())

    assert result.parts == ()
    assert result.failure == "download"


@pytest.mark.asyncio
async def test_im_fetcher_scopes_credentials_to_protected_origin_and_current_agent(
    monkeypatch,
):
    import httpx
    from personal_assistant.gateway.image_attachments import build_im_attachment_fetcher

    seen = []
    token = "runtime-first"

    async def current_token():
        return token

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200, content=_PNG_BYTES, headers={"Content-Type": "image/png"}
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(**kwargs, transport=httpx.MockTransport(handler)),
    )
    fetch = build_im_attachment_fetcher(
        base_url="http://im.local", token_getter=current_token
    )
    resolver = ImageAttachmentResolver(fetcher=fetch)
    path = "/im/v1/conversations/chat/images/" + "a" * 32
    result = await resolver.resolve([{"url": path}], agent_id="agent-a")
    assert result.failure is None
    assert seen[0].headers["Authorization"] == "Bearer runtime-first"
    assert seen[0].url.params["agent_id"] == "agent-a"
    for url in (
        "https://external.example/photo.png",
        "http://im.local/public.png",
        "http://user:pass@im.local" + path,
        "http://im.local.evil" + path,
        path + "?secret=hidden",
        path + "/../file",
        path.replace("/chat/", "/%63hat/"),
        "http://127.0.0.1/secret",
        "//im.local" + path,
    ):
        result = await resolver.resolve([{"url": url}], agent_id="agent-a")
        assert result.failure == "download"
    assert len(seen) == 1
    token = "runtime-next"
    await fetch(path, "agent-b")
    assert seen[-1].headers["Authorization"] == "Bearer runtime-next"
    assert seen[-1].url.params["agent_id"] == "agent-b"
    token = None
    assert (
        await resolver.resolve([{"url": path}], agent_id="agent-a")
    ).failure == "download"
    assert len(seen) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,headers,body",
    [
        (302, {"Location": "http://127.0.0.1/secret"}, b""),
        (200, {"Content-Type": "text/html"}, _PNG_BYTES),
        (200, {"Content-Type": "image/jpeg"}, _PNG_BYTES),
        (200, {"Content-Type": "image/png", "Content-Length": "99999999"}, _PNG_BYTES),
        (200, {"Content-Type": "image/png"}, _PNG_BYTES * 10),
    ],
)
async def test_im_fetcher_rejects_redirect_mime_and_stream_limits(
    monkeypatch, status, headers, body
):
    import httpx
    from personal_assistant.gateway.image_attachments import build_im_attachment_fetcher

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(
            **kwargs,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, headers=headers, content=body)
            ),
        ),
    )

    async def token():
        return "machine"

    fetch = build_im_attachment_fetcher(
        base_url="http://im.local", token_getter=token, max_image_bytes=len(_PNG_BYTES)
    )
    with pytest.raises(ValueError):
        await fetch("/im/v1/conversations/chat/images/" + "a" * 32, "agent-a")
