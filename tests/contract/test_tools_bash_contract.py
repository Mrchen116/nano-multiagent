from pathlib import Path
import signal

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
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _context(tmp_path: Path) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path)


def _wired_bash_tool(tmp_path: Path) -> BashTool:
    """A BashTool on the production wired path (ShellRunner foreground engine).

    bugfix-417-M4 (decision 8): the dead no-wiring path (_run_legacy_sync) was deleted,
    so these contracts now exercise the engine production actually uses. ``runs_registry
    =None`` skips background notification wiring (irrelevant to foreground bash) while
    still handing the tool a real ShellRunner.
    """
    wiring = wire_background_tasks(workspace_root=tmp_path, runs_registry=None)
    assert isinstance(wiring.bash_runner, ShellRunner)
    return BashTool(wiring=wiring)


def test_bash_timeout_contract_exposes_stable_details(tmp_path: Path) -> None:
    """A bash command hitting its own deadline surfaces stable timeout details on the
    production wired path: message, timedOut, timeout, reason_code=tool_timeout."""
    tool = _wired_bash_tool(tmp_path)
    with pytest.raises(ToolError, match="Command timed out after") as exc_info:
        tool.run(
            {
                "command": "python3 -c \"import time; print('before', flush=True); time.sleep(5)\"",
                "timeout": 0.3,
            },
            _context(tmp_path),
        )

    details = exc_info.value.details
    assert details["timedOut"] is True
    assert details["timeout"] == 0.3
    # bugfix-417-M4 (decision 5): the tool's own deadline → tool_timeout badge.
    assert details["reason_code"] == "tool_timeout"
    assert details["tool_name"] == "bash"


def test_bash_signal_contract_exposes_signal_details(tmp_path: Path) -> None:
    """A bash command killed by a signal surfaces stable signal details on the
    production wired path."""
    tool = _wired_bash_tool(tmp_path)
    with pytest.raises(ToolError, match="Command exited with code") as exc_info:
        tool.run(
            {
                "command": 'python3 -c "import os,signal; os.kill(os.getpid(), signal.SIGTERM)"',
            },
            _context(tmp_path),
        )

    details = exc_info.value.details
    assert details["exitCode"] == -signal.SIGTERM
    assert details["signal"] == "SIGTERM"
    assert details["signalNumber"] == signal.SIGTERM
    assert details["tool_name"] == "bash"


# bugfix-417-M4 (decision 8): the bash line/byte truncation + fullOutputPath contract
# lived ONLY on the deleted dead path (_run_legacy_sync). The production wired path has
# always relied on the downstream result-budget system for oversized output (covered by
# tests/unit/test_tool_result_budget.py), so no bash-tool-level truncation contract test
# remains here.
