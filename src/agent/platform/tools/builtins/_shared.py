"""Shared helpers for platform builtins.

Internal to the builtins package — not part of the platform.tools public API.
"""

from typing import Any


def _normalize_optional_text(value: Any) -> str | None:
    """Return the stripped string if *value* is a non-empty str, else None.

    Two builtins (task, agent) each carried a private copy — consolidated here
    as refactor-395-M1.

    Args:
        value: Arbitrary value from a tool args dict.

    Returns:
        The stripped string, or None if value is not a str or is blank.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text
