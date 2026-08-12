"""Parse the model-capability-derived session effort command."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EffortCommand:
    """Represent one syntactically recognized ``/effort`` command."""

    value: str | None


def parse_effort_command(text: str) -> EffortCommand | None:
    """Parse ``/effort`` without imposing product-specific level names.

    Validation of the value belongs to the current session's SDK model capability
    catalog, because distinct models may expose different level sets.
    """

    parts = text.strip().split()
    if not parts or parts[0] != "/effort":
        return None
    return EffortCommand(value=parts[1] if len(parts) == 2 else None)


__all__ = ["EffortCommand", "parse_effort_command"]
