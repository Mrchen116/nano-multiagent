"""Shared low-level helpers for LLM provider implementations.

Providers (anthropic, openai_compat) each carried a private copy of
extract_non_negative_int — consolidated here as refactor-395-M1.
"""

from typing import Any


def extract_non_negative_int(value: Any) -> int | None:
    """Return *value* as a non-negative int, or None if invalid.

    Rejects booleans (Python's bool is a subclass of int) and negative values.

    Args:
        value: Arbitrary value from a JSON payload.

    Returns:
        The integer if it is a non-negative int; None otherwise.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None
