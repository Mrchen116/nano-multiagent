"""Shared attachment classification and honest descriptions of unread content."""

from collections.abc import Mapping
import json
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse


_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
    ".tif",
    ".tiff",
    ".heic",
    ".avif",
}


def is_image_attachment(attachment: Mapping[str, Any]) -> bool:
    """Classify a descriptor without granting access or validating its bytes.

    Args:
        attachment: Inbound attachment metadata with optional MIME and file name.

    Returns:
        Whether existing image resolution should validate the attachment.
    """
    url = str(attachment.get("url") or "")
    mime = str(attachment.get("content_type") or "").split(";", 1)[0].strip().lower()
    if url.lower().startswith("data:image/"):
        return True
    if mime and mime != "application/octet-stream":
        return mime.startswith("image/")
    path = urlparse(url).path
    name = str(attachment.get("file_name") or path)
    return PurePosixPath(name.lower()).suffix in _IMAGE_SUFFIXES or "/images/" in path


def unread_attachment_text(
    attachment: Mapping[str, Any], *, image_failure: str | None = None
) -> dict[str, Any]:
    """Describe a source honestly without claiming to have read its content.

    Args:
        attachment: Source descriptor; credentials must never be added to it.
        image_failure: Stable reason when a historical image could not be read.

    Returns:
        SDK text part with a source reference and explicit unread status.
    """
    descriptor = {
        key: attachment[key]
        for key in ("file_name", "content_type", "url")
        if attachment.get(key)
    }
    status = (
        f"历史图片内容未读取（{image_failure}）；不可据此推断图片内容，可重新发送。"
        if image_failure
        else "普通文件内容未读取；当前入口未自动解析文件内容，可提供正文。来源引用不代表已获得读取权限。"
    )
    return {
        "type": "text",
        "text": status + "\n" + json.dumps(descriptor, ensure_ascii=False),
    }
