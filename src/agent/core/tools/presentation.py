"""Tool presentation protocol for user-facing SSE events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ToolPresentationEvent:
    """User-facing tool render payload, attached to tool_start / tool_end SSE."""

    visible: bool = False
    label: str = ""
    summary: str = ""
    detail: Mapping[str, Any] | None = None
    # feat-425 决策 1: 让"展示随工具走"覆盖 emoji——工具/presenter 自带的折叠行图标,
    # 经事件全程透传 + 落库。空串 = 工具未声明,前端按 name→emoji 名表兜底(内置工具
    # 不退化,DIY/MCP 拿通用 🔧)。
    emoji: str = ""


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
