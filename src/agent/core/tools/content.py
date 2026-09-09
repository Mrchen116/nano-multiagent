"""Canonical identity for model-visible tool result content."""

import hashlib
import json
from typing import Any


def tool_content_digest(content: Any) -> str:
    """Digest final model content using canonical UTF-8 JSON.

    Args:
        content: Actual string or multimodal blocks supplied to the model.

    Returns:
        SHA-256 digest prefixed with ``sha256:``.

    Raises:
        ValueError: Content includes non-finite numbers.
        TypeError: Content is not JSON serializable.
    """
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
