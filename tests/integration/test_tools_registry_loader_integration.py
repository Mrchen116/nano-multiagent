from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.loader import discover_tool_files, load_tools_from_directory
from agent.platform.tools.registry import ToolRegistry


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

    result = registry.execute("echo", {"text": "hi"})

    assert result["echo"] == "hi"
    with pytest.raises(ToolError, match="missing required"):
        registry.execute("echo", {})
    with pytest.raises(ToolError, match="unknown tool"):
        registry.execute("missing", {})


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
    assert registry.execute("reverse", {"text": "abc"})["text"] == "cba"

