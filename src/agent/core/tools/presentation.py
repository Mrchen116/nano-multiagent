"""Tool presentation protocol for user-facing SSE events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ToolPresentationEvent:
    """User-facing tool render payload, attached to tool_start / tool_end SSE."""

    visible: bool = False
    label: str = ""
    summary: str = ""
    detail: Mapping[str, Any] | None = None


class ToolPresenter(Protocol):
    """Per-tool user-facing render strategy. Pure function, no IO."""

    def format_start(
        self,
        args: Mapping[str, Any],
    ) -> ToolPresentationEvent: ...

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent: ...
