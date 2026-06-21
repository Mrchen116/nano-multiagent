import asyncio
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.platform.background_tasks.shell_runner import ShellRunner
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _wired_bash_tool(tmp_path: Path) -> BashTool:
    """A BashTool on the production wired path (ShellRunner foreground engine).

    bugfix-417-M4 (decision 8): the dead no-wiring path was deleted; these integration
    contracts now run through the engine production actually uses.
    """
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=None)
    assert isinstance(wiring.bash_runner, ShellRunner)
    return BashTool(wiring=wiring)


def test_registry_bash_signal_error_keeps_signal_details(tmp_path: Path) -> None:
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(_wired_bash_tool(tmp_path))

    with pytest.raises(ToolError, match="Command exited with code") as exc_info:
        asyncio.run(
            registry.execute(
                "bash",
                {
                    "command": 'python3 -c "import os,signal; os.kill(os.getpid(), signal.SIGTERM)"'
                },
            )
        )

    details = exc_info.value.details
    assert details["tool_name"] == "bash"
    assert details["signal"] == "SIGTERM"
    assert details["signalNumber"] == 15
