from .bash import BashTool
from .edit import EditTool
from .read import ReadTool
from .write import WriteTool


def builtin_tools() -> tuple[object, ...]:
    return (ReadTool(), WriteTool(), EditTool(), BashTool())


def register_builtin_tools(registry) -> None:  # noqa: ANN001
    for tool in builtin_tools():
        registry.register(tool)
