"""Resolve Gateway image attachments into self-contained Kernel input parts."""

from __future__ import annotations

import asyncio
import base64
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from personal_assistant.gateway.im_http_transport import (
    build_im_http_headers,
    normalize_im_http_base_url,
)


ImageFailureKind = Literal["download", "oversize", "corrupt"]
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ImageResolution:
    """Describe the all-or-nothing result of resolving image attachments.

    Args:
        parts: Kernel image parts in input order; empty when resolution failed.
        failure: Stable failure kind for user-visible handling, or ``None`` on success.
    """

    parts: tuple[dict[str, Any], ...]
    failure: ImageFailureKind | None = None


class ImageAttachmentResolver:
    """Own image fetch, limit, validation, MIME and data-URL policy.

    Args:
        fetcher: Optional downloader accepting a URL and executing Agent identity.
            Without one, only validated data images are accepted.
        max_image_bytes: Inclusive maximum accepted downloaded payload size.
    """

    def __init__(
        self,
        *,
        fetcher: Callable[[str, str], Awaitable[bytes]] | None = None,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    ) -> None:
        if max_image_bytes <= 0:
            raise ValueError("max_image_bytes must be > 0")
        self._fetcher = fetcher
        self._max_image_bytes = max_image_bytes

    async def resolve(
        self, attachments: object, *, agent_id: str = ""
    ) -> ImageResolution:
        """Resolve every valid attachment descriptor or fail the whole image set.

        Args:
            attachments: Raw inbound metadata value expected to contain attachment dicts.
            agent_id: Executing Agent identity for protected IM resource access.

        Returns:
            Ordered Kernel image parts, or an empty set with the first stable failure kind.
        """

        if not isinstance(attachments, list) or not attachments:
            return ImageResolution(parts=())
        parts: list[dict[str, Any]] = []
        for item in attachments:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            url = item["url"]
            mime = item.get("content_type")
            mime = mime.strip() if isinstance(mime, str) and mime.strip() else None
            if url.startswith("data:image/"):
                if len(url) > (self._max_image_bytes + 2) // 3 * 4 + 64:
                    return ImageResolution(parts=(), failure="oversize")
                raw = _decode_image_data_url(url)
                if raw is None:
                    return ImageResolution(parts=(), failure="corrupt")
                if len(raw) > self._max_image_bytes:
                    return ImageResolution(parts=(), failure="oversize")
                detected_mime = _detect_image_mime(raw)
                if (
                    detected_mime is None
                    or url.partition(";")[0] != f"data:{detected_mime}"
                ):
                    return ImageResolution(parts=(), failure="corrupt")
                canonical_url = f"data:{detected_mime};base64," + base64.b64encode(
                    raw
                ).decode("ascii")
                parts.append(
                    {
                        "type": "image",
                        "image_url": canonical_url,
                        "mime_type": detected_mime,
                    }
                )
                continue
            if self._fetcher is None:
                return ImageResolution(parts=(), failure="download")
            try:
                raw = await self._fetcher(url, agent_id)
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).info(
                    "image attachment download failed (%s)", type(exc).__name__
                )
                return ImageResolution(parts=(), failure="download")
            if not isinstance(raw, (bytes, bytearray)) or not raw:
                return ImageResolution(parts=(), failure="download")
            if len(raw) > self._max_image_bytes:
                return ImageResolution(parts=(), failure="oversize")
            detected_mime = _detect_image_mime(bytes(raw))
            if detected_mime is None:
                return ImageResolution(parts=(), failure="corrupt")
            data_url = f"data:{detected_mime};base64," + base64.b64encode(
                bytes(raw)
            ).decode("ascii")
            parts.append(
                {
                    "type": "image",
                    "image_url": data_url,
                    "mime_type": detected_mime,
                }
            )
        return ImageResolution(parts=tuple(parts))


def _decode_image_data_url(url: str) -> bytes | None:
    header, separator, encoded = url.partition(",")
    if not separator or not re.fullmatch(
        r"data:image/(?:png|jpeg|gif|webp);base64", header
    ):
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError:
        return None


def build_im_attachment_fetcher(
    *,
    base_url: str,
    token_getter: Callable[[], Awaitable[str | None]],
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> Callable[[str, str], Awaitable[bytes]]:
    """Download images, authenticating only this IM's protected resource URLs.

    Args:
        base_url: Configured IM origin.
        token_getter: Current registered node credential provider.

    Returns:
        Downloader accepting the source URL and executing Agent identity.
    """
    base = normalize_im_http_base_url(base_url)
    origin = urlparse(base)

    async def fetch(url: str, agent_id: str) -> bytes:
        parsed = urlparse(url)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("image source credentials are forbidden")
        if parsed.query or parsed.fragment or "\\" in url:
            raise ValueError("image source must be a canonical attachment URL")
        if parsed.netloc or parsed.scheme:
            if (
                parsed.scheme,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            ) != (
                origin.scheme,
                origin.hostname,
                origin.port or (443 if origin.scheme == "https" else 80),
            ):
                raise ValueError("image source must belong to this IM")
        if not re.fullmatch(
            r"/im/v1/conversations/[A-Za-z0-9_-]+/(?:images|attachments)/[0-9a-f]{32}",
            parsed.path,
        ):
            raise ValueError("image source must be a protected attachment")
        target = f"{origin.scheme}://{origin.netloc}{parsed.path}"
        token = await token_getter()
        if not token or not agent_id:
            raise ConnectionError(
                "IM resource access requires registered Agent identity"
            )
        async with asyncio.timeout(30.0):
            async with httpx.AsyncClient(
                timeout=10.0, trust_env=False, follow_redirects=False
            ) as client:
                async with client.stream(
                    "GET",
                    target,
                    headers=build_im_http_headers(token),
                    params={"agent_id": agent_id},
                ) as response:
                    if response.status_code != 200:
                        raise ValueError(
                            "image source did not return a direct successful response"
                        )
                    declared = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if declared not in {
                        "image/png",
                        "image/jpeg",
                        "image/gif",
                        "image/webp",
                    }:
                        raise ValueError("image source returned unsupported MIME")
                    length = response.headers.get("content-length")
                    if length and int(length) > max_image_bytes:
                        raise ValueError("image source exceeds size limit")
                    data = bytearray()
                    async for chunk in response.aiter_bytes(64 * 1024):
                        if len(data) + len(chunk) > max_image_bytes:
                            raise ValueError("image source exceeds size limit")
                        data.extend(chunk)
                    result = bytes(data)
                    if _detect_image_mime(result) != declared:
                        raise ValueError("image MIME does not match its bytes")
                    return result

    return fetch


def _detect_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png" if _png_is_structurally_valid(data) else None
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg" if b"\xff\xd9" in data[3:] else None
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif" if data.endswith(b"\x3b") else None
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 12:
        riff_size = int.from_bytes(data[4:8], "little")
        return "image/webp" if riff_size + 8 <= len(data) else None
    return None


def _png_is_structurally_valid(data: bytes) -> bool:
    # The shortest complete PNG is signature + IHDR + IEND (45 bytes). Requiring
    # those structural anchors prevents magic-only payloads reaching the provider.
    return len(data) >= 45 and data[12:16] == b"IHDR" and b"IEND" in data
