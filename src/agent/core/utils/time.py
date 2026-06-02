"""UTC timestamp utility shared across agent.core.

Five modules (runtime, events.hub, runs.registry, session.jsonl_store,
session.entries) each carried a private _utc_now_iso copy — consolidated here
as refactor-395-M1.
"""

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Returns:
        A string like '2026-06-02T10:00:00.123456+00:00'.
    """
    return datetime.now(UTC).isoformat()
