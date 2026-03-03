"""Registration helpers for built-in tools."""

from typing import Any

from .bash import BashTool
from .edit import EditTool
from .read import ReadTool
from .task import TaskTool
from .write import WriteTool


def builtin_tools(*, runtime: Any | None = None) -> tuple[object, ...]:
    """Return built-in tool instances in the canonical registration order."""

    return (ReadTool(), WriteTool(), EditTool(), BashTool(), TaskTool(runtime=runtime))


def register_builtin_tools(registry, *, runtime: Any | None = None) -> None:  # noqa: ANN001
    """Register all built-in tools into the provided registry."""

    for tool in builtin_tools(runtime=runtime):
        registry.register(tool)
