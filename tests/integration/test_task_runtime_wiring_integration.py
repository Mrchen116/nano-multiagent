from pathlib import Path

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.tools.loader import build_tool_registry


def test_task_tool_is_registered_and_validated_by_registry(tmp_path: Path) -> None:
    registry = build_tool_registry(repo_root=tmp_path)

    with pytest.raises(ToolError, match="missing required argument: run_in_background"):
        registry.execute("task", {})
