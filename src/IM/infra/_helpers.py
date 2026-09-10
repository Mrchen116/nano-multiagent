"""Shared low-level helpers for IM infra layer (db and repositories).

Internal to IM.infra — not part of the IM public API.
Consolidated from private copies in db.py and repositories.py as refactor-395-M1.
"""

import re


def _text_preview(content: str) -> str:
    """Show image labels, never image destinations, in the plain-text inbox."""
    return re.sub(
        r"!\[([^\]\n]*)\]\(\s*(?:<[^>\n]+>|[^\s)]+)\s*\)",
        lambda match: f"[{match[1].strip() or '图片'}]",
        content.strip(),
    )


def _optional_text(value: object) -> str | None:
    """Return the stripped string if *value* is a non-empty str, else None.

    Non-str values (including None) are silently mapped to None — callers in the
    infra layer rely on this quiet fallback when deserialising nullable DB columns.

    Args:
        value: Arbitrary value from a JSON payload or SQLite row.

    Returns:
        The stripped string, or None if value is not a str or is blank.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _is_no_reply_protocol_token(value: str | None) -> bool:
    """Return True if *value* is the no-reply suppression protocol token.

    Args:
        value: A nullable string (typically a message preview candidate).

    Returns:
        True when the value matches the NO_REPLY protocol marker.
    """
    if value is None:
        return False
    normalized = value.strip()
    return (
        normalized == "NO_REPLY"
        or normalized.startswith("suppressed_by=no_reply_token")
        or "suppressed_by=no_reply_token" in normalized
    )


def _preview_from_event(event_type: str, payload: dict[str, object]) -> str | None:
    """Derive a short human-readable preview string from one event payload.

    Two infra modules (db, repositories) each carried a private copy —
    consolidated here as refactor-395-M1. The repositories copy used
    keyword-only args; both call-sites are updated to use positional form.

    Args:
        event_type: The event type string (e.g. 'message.sent').
        payload: The event payload dict.

    Returns:
        A preview string, or None if no suitable content is found.
    """
    content = _optional_text(payload.get("content"))
    if (
        event_type in {"message.sent", "message_created", "message.completed"}
        and content is not None
    ):
        # A completed body can replace provisional relay summaries after channel
        # projection; inbox and startup replay must use that same final content.
        return _text_preview(content)

    if event_type in {
        "relay.processing",
        "relay.report",
        "relay.completed",
        "relay.failed",
        "message.delivered",
    }:
        summary = _optional_text(payload.get("summary"))
        detail = _optional_text(payload.get("detail"))
        preview = summary or detail or content
        if preview is None or _is_no_reply_protocol_token(preview):
            return None
        return _text_preview(preview)

    file_name = _optional_text(payload.get("file_name"))
    if file_name is not None:
        return file_name
    attachments = payload.get("attachments")
    if isinstance(attachments, list) and attachments:
        return "Attachment"
    return None
