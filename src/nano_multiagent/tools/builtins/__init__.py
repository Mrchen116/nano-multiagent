from typing import Any

from .bash import BashTool
from .edit import EditTool
from .read import ReadTool
from .task import TaskTool
from .write import WriteTool


def builtin_tools(*, runtime: Any | None = None) -> tuple[object, ...]:
    return (ReadTool(), WriteTool(), EditTool(), BashTool(), TaskTool(runtime=runtime))


def register_builtin_tools(registry, *, runtime: Any | None = None) -> None:  # noqa: ANN001
    for tool in builtin_tools(runtime=runtime):
        registry.register(tool)
