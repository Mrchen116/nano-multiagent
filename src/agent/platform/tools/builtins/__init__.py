"""Canonical registration helpers for platform-owned built-in tools.

Self-evolution tools (skill_manage, memory) are exported from this module but
require resolved filesystem paths injected at bootstrap time.  They are NOT
included in the default ``builtin_tools()`` tuple — product bootstrap (M3)
instantiates and registers them alongside the default set after resolving
skill_root / memory_root from the active ConfigResolver.
"""

from typing import Any

from .agent import AgentTool
from .bash import BashTool
from .edit import EditTool
from .memory import MemoryTool
from .read import ReadTool
from .skill_manage import SkillManageTool
from .task_stop import TaskStopTool
from .web_fetch import WebFetchTool
from .write import WriteTool

# MemoryTool and SkillManageTool are not in builtin_tools() (they need path-resolved args),
# but they ARE exported here for product bootstrap to import without knowing the submodule.
__all__ = [
    "AgentTool",
    "BashTool",
    "EditTool",
    "MemoryTool",
    "ReadTool",
    "SkillManageTool",
    "TaskStopTool",
    "WebFetchTool",
    "WriteTool",
    "builtin_tools",
    "register_builtin_tools",
]


def builtin_tools(
    *,
    runtime: Any | None = None,
    wiring: Any | None = None,
) -> tuple[object, ...]:
    """Return built-in tool instances in the canonical registration order.

    Note: ``SkillManageTool`` and ``MemoryTool`` are NOT included here because
    they need path-resolved constructor arguments (skill_root, memory_root).
    Product bootstrap instantiates and registers them separately.
    """

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
