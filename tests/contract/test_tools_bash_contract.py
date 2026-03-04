from pathlib import Path
import signal

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.bash import BashTool
from nano_multiagent.tools.safety import ToolSafetyConfig


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def test_bash_truncation_contract_exposes_full_output_path(tmp_path: Path) -> None:
    result = BashTool().run(
        {"command": "python -c \"[print(f'line-{i}') for i in range(8)]\""},
        _context(
            tmp_path,
            config=ToolSafetyConfig(bash_max_output_lines=2, bash_max_output_bytes=200),
        ),
    )

    assert set(result.keys()) == {
        "command",
        "exitCode",
        "content",
        "truncated",
        "fullOutputPath",
    }
    assert result["truncated"] is True
    assert isinstance(result["fullOutputPath"], str)
    assert result["fullOutputPath"] in result["content"]
    assert "[Showing lines " in result["content"]
    assert "Full output: " in result["content"]
    assert Path(result["fullOutputPath"]).exists()


def test_bash_timeout_contract_exposes_stable_details(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="timed out") as exc_info:
        BashTool().run(
            {"command": "python -c \"import time;time.sleep(0.3)\"", "timeout": 0.05},
            _context(tmp_path),
        )

    details = exc_info.value.details
    assert details["timed_out"] is True
    assert details["timeout"] == 0.05
    assert details["tool_name"] == "bash"


def test_bash_signal_contract_exposes_signal_details(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="terminated by signal") as exc_info:
        BashTool().run(
            {
                "command": "python -c \"import os,signal; os.kill(os.getpid(), signal.SIGTERM)\"",
            },
            _context(tmp_path),
        )

    details = exc_info.value.details
    assert details["exit_code"] == -signal.SIGTERM
    assert details["signal"] == "SIGTERM"
    assert details["signal_number"] == signal.SIGTERM
    assert details["tool_name"] == "bash"
