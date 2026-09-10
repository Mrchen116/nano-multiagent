"""Stable compact identifiers for IM chat entities."""

import secrets
import string


def new_chat_id(prefix: str) -> str:
    """Generate an ID; the owning table enforces uniqueness at insertion."""
    return prefix + "".join(
        secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
    )
