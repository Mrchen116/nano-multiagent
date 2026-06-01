import asyncio
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.platform.tools.base import ToolContext
from agent.platform.tools.loader import discover_tool_files, load_tools_from_directory
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class EchoTool:
    name = "echo"
    description = "Echo input"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        return {"echo": args["text"], "cwd": str(ctx.cwd)}


def test_registry_dispatches_and_validates_arguments(tmp_path: Path) -> None:
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(EchoTool())

    result = asyncio.run(registry.execute("echo", {"text": "hi"}))

    assert result["echo"] == "hi"
    with pytest.raises(ToolError, match="missing required"):
        asyncio.run(registry.execute("echo", {}))
    with pytest.raises(ToolError, match="unknown tool"):
        asyncio.run(registry.execute("missing", {}))


def test_loader_discovers_and_registers_directory_tools(tmp_path: Path) -> None:
    tools_dir = tmp_path / ".nano" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "reverse_tool.py").write_text(
        """
class ReverseTool:
    name = \"reverse\"
    description = \"Reverse text\"
    input_schema = {
        \"type\": \"object\",
        \"properties\": {\"text\": {\"type\": \"string\"}},
        \"required\": [\"text\"],
        \"additionalProperties\": False,
    }

    def run(self, args, ctx):
        return {\"text\": args[\"text\"][::-1]}

TOOL = ReverseTool()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    files = discover_tool_files(tmp_path)
    loaded_names = load_tools_from_directory(repo_root=tmp_path, registry=registry)

    assert len(files) == 1
    assert files[0].name == "reverse_tool.py"
    assert "reverse" in loaded_names
    assert asyncio.run(registry.execute("reverse", {"text": "abc"}))["text"] == "cba"
