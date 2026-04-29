"""Canonical registration helpers for platform-owned built-in tools."""

from typing import Any

from .agent import AgentTool
from .bash import BashTool
from .edit import EditTool
from .read import ReadTool
from .task_stop import TaskStopTool
from .web_fetch import WebFetchTool
from .write import WriteTool


def builtin_tools(
    *,
    runtime: Any | None = None,
    wiring: Any | None = None,
) -> tuple[object, ...]:
    """Return built-in tool instances in the canonical registration order."""

    return (
        ReadTool(),
        WriteTool(),
        EditTool(),
        BashTool(wiring=wiring),
        AgentTool(runtime=runtime, wiring=wiring),
        TaskStopTool(wiring=wiring),
        WebFetchTool(),
    )


def register_builtin_tools(
    registry,
    *,
    runtime: Any | None = None,
    wiring: Any | None = None,
) -> None:  # noqa: ANN001
    """Register all built-in tools into the provided registry."""

    for tool in builtin_tools(runtime=runtime, wiring=wiring):
        registry.register(tool)
