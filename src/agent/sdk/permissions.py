"""Generic permission decisions for SDK consumers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionOutcome:
    """Permission decision without executing a tool operation."""

    allowed: bool
    reason: str | None = None
