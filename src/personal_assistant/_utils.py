"""Shared low-level helpers for the personal_assistant package.

Internal to personal_assistant — not part of the agent.sdk public API.
Consolidated from private copies as refactor-395-M1.
"""


def _require_text(value: object, *, field_name: str) -> str:
    """Return *value* stripped if it is a non-empty str, else raise ValueError.

    Three modules (ws/im_connection, config/sync_client, channels/web_relay_adapter)
    each carried a private copy that raises ValueError — consolidated here.
    Note: personal_assistant/main.py carries a RuntimeError variant that is left
    in-place because changing its exception type would alter its callers' behaviour.

    Args:
        value: Arbitrary value from a parsed message payload.
        field_name: Human-readable field label used in the error message.

    Returns:
        The stripped string.

    Raises:
        ValueError: If value is not a non-empty string.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    """Return stripped *value* if it is a non-empty str; return None if it is None;
    raise ValueError for any other type.

    channels/web_relay_adapter carried a private copy — consolidated here.
    (The IM infra layer's _optional_text silently returns None for non-str values;
    this PA version intentionally raises to surface protocol violations early.)

    Args:
        value: Arbitrary value from a parsed message payload.

    Returns:
        The stripped string, or None.

    Raises:
        ValueError: If value is neither None nor a str.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings when provided")
    stripped = value.strip()
    return stripped or None
