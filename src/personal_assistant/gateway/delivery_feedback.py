"""Product-owned delivery correction input and durable admission budget seam."""

from typing import Protocol


class DeliveryFeedbackBudget(Protocol):
    """Persist the two admitted corrections of one logical product request."""

    def next_submission(self, logical_request_id: str) -> tuple[str, int] | None:
        """Return the stable next identity and ordinal, or None when exhausted."""
        ...

    def record_admitted(self, logical_request_id: str, submission_id: str) -> None:
        """Consume one budget slot idempotently after Kernel admission succeeds."""
        ...


def feedback_parts(reminder: str, ordinal: int) -> list[dict[str, object]]:
    """Keep delivery diagnostics system-sourced and make the last repair text-only."""
    if ordinal == 2:
        reminder += (
            "\n<system-reminder>This is the final delivery correction. "
            "Respond with plain text explaining that the image could not be delivered. "
            "Do not include images, image references, or attempt another image delivery."
            "</system-reminder>"
        )
    return [{"type": "text", "text": reminder, "context_origin": "system"}]
