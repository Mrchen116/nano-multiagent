from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def test_registry_executes_bash_with_truncation_and_persisted_output(tmp_path: Path) -> None:
    registry = ToolRegistry(
        context=ToolContext.create(
            repo_root=tmp_path,
            safety_config=ToolSafetyConfig(bash_max_output_lines=2, bash_max_output_bytes=200),
        )
    )
    registry.register(BashTool())

    result = registry.execute(
        "bash",
        {"command": "python -c \"[print(f'line-{i}') for i in range(8)]\""},
    )

    assert result["truncated"] is True
    assert "fullOutputPath" in result
    assert isinstance(result["fullOutputPath"], str)
    assert result["stdout"]
    output = Path(result["fullOutputPath"]).read_text(encoding="utf-8")
    assert "line-0" in output
    assert "line-7" in output


def test_registry_bash_signal_error_keeps_signal_details(tmp_path: Path) -> None:
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(BashTool())

    with pytest.raises(ToolError, match="Command exited with code") as exc_info:
        registry.execute(
            "bash",
            {"command": "python -c \"import os,signal; os.kill(os.getpid(), signal.SIGTERM)\""},
        )

    details = exc_info.value.details
    assert details["tool_name"] == "bash"
    assert details["signal"] == "SIGTERM"
    assert details["signalNumber"] == 15
