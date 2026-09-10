"""Public identity format for final model-visible tool content."""

from typing import Any

from agent.core.tools.content import tool_content_digest as _tool_content_digest


def tool_content_digest(content: Any) -> str:
    """Compute the canonical digest used by tool_result_committed proofs.

    Args:
        content: Actual string or multimodal content blocks returned to the model.

    Returns:
        ``sha256:<hex>`` over UTF-8 JSON with sorted object keys, compact separators,
        and Unicode preserved. Image data participates as supplied.

    Raises:
        TypeError: Content is not JSON serializable.
        ValueError: Content contains non-finite numbers.
    """
    return _tool_content_digest(content)
