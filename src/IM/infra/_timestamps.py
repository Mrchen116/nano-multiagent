"""Canonical UTC text timestamps shared by persistence and watchdog code."""

from datetime import datetime, timezone


def format_utc(dt: datetime) -> str:
    """Format a timezone-aware datetime using the canonical SQLite UTC text."""
    if dt.tzinfo is None:
        raise ValueError("format_utc requires a timezone-aware datetime")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_now() -> str:
    """Return the current UTC timestamp in canonical storage format."""
    return format_utc(datetime.now(timezone.utc))
