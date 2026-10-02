"""Shared HTTP projection for bounded attachment storage failures."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import HTTPException, Request

from IM.infra.repositories.message_images import (
    AttachmentBusyError,
    AttachmentCapacityError,
    AttachmentTooLargeError,
)


def upload_error(exc: ValueError) -> HTTPException:
    """Map storage rejections without exposing capacity details to members."""
    if isinstance(exc, AttachmentBusyError):
        return HTTPException(
            429, "attachment upload busy", headers={"Retry-After": "2"}
        )
    if isinstance(exc, AttachmentCapacityError):
        return HTTPException(507, "attachment upload unavailable")
    if isinstance(exc, AttachmentTooLargeError):
        return HTTPException(413, str(exc))
    return HTTPException(409, str(exc))


def image_content_type(data: bytes) -> str | None:
    """Identify supported raster families from bytes rather than client metadata."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def upload_chunks(request: Request) -> AsyncIterator[bytes]:
    """Bound upload wall time as well as bytes so slow clients release their slots."""
    try:
        async with asyncio.timeout(60):
            async for chunk in request.stream():
                yield chunk
    except TimeoutError as exc:
        raise HTTPException(408, "attachment upload timed out; retry") from exc
