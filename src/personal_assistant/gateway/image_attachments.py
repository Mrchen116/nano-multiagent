"""Resolve Gateway image attachments into self-contained Kernel input parts."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, Literal


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
        fetcher: Optional asynchronous URL downloader. Without one, valid attachment
            descriptors pass through as raw URLs for product-agnostic/test wiring.
        max_image_bytes: Inclusive maximum accepted downloaded payload size.
    """

    def __init__(
        self,
        *,
        fetcher: Callable[[str], Awaitable[bytes]] | None = None,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    ) -> None:
        if max_image_bytes <= 0:
            raise ValueError("max_image_bytes must be > 0")
        self._fetcher = fetcher
        self._max_image_bytes = max_image_bytes

    async def resolve(self, attachments: object) -> ImageResolution:
        """Resolve every valid attachment descriptor or fail the whole image set.

        Args:
            attachments: Raw inbound metadata value expected to contain attachment dicts.

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
            if self._fetcher is None:
                part: dict[str, Any] = {"type": "image", "image_url": url}
                if mime:
                    part["mime_type"] = mime
                parts.append(part)
                continue
            try:
                raw = await self._fetcher(url)
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


def _detect_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png" if _png_is_structurally_valid(data) else None
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg" if data.rstrip(b"\x00").endswith(b"\xff\xd9") else None
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
