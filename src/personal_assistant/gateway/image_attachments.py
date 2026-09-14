"""Resolve Gateway image attachments into self-contained Kernel input parts."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

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
            Without one, descriptors pass through as raw URLs for standalone wiring.
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
                raw = _decode_image_data_url(url)
                if raw is None:
                    return ImageResolution(parts=(), failure="corrupt")
                if len(raw) > self._max_image_bytes:
                    return ImageResolution(parts=(), failure="oversize")
                detected_mime = _detect_image_mime(raw)
                if detected_mime is None:
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
                part: dict[str, Any] = {"type": "image", "image_url": url}
                if mime:
                    part["mime_type"] = mime
                parts.append(part)
                continue
            try:
                raw = await self._fetcher(url, agent_id)
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).info(
                    "image attachment download failed (%s): %s", url, exc
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
    if not separator or ";base64" not in header.lower():
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError:
        return None


def build_im_attachment_fetcher(
    *, base_url: str, token_getter: Callable[[], Awaitable[str | None]]
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
        target = urljoin(base + "/", url)
        parsed = urlparse(target)
        protected = (
            (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc)
            and parsed.path.startswith("/im/v1/conversations/")
            and any(part in parsed.path for part in ("/images/", "/attachments/"))
        )
        headers = {}
        params = None
        if protected:
            token = await token_getter()
            if not token or not agent_id:
                raise ConnectionError(
                    "IM resource access requires registered Agent identity"
                )
            headers = build_im_http_headers(token)
            params = {"agent_id": agent_id}
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            response = await client.get(target, headers=headers, params=params)
            response.raise_for_status()
            return response.content

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
