from pathlib import Path
import base64

from nano_multiagent.hooks.context import HookContext
from nano_multiagent.hooks.registry import HookRegistry
from nano_multiagent.hooks.runner import HookRunner
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.read import ReadTool
from nano_multiagent.tools.registry import ToolRegistry
from nano_multiagent.tools.safety import ToolSafetyConfig


def test_registry_executes_read_image_and_keeps_part_structure(tmp_path: Path) -> None:
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWkAAAAASUVORK5CYII="
    )
    (tmp_path / "pixel.png").write_bytes(image_bytes)
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(ReadTool())

    result = registry.execute("read", {"path": "pixel.png"})

    assert isinstance(result["content"], list)
    assert [part["type"] for part in result["content"]] == ["text", "image"]
    assert result["content"][1]["image_url"].startswith("data:image/png;base64,")


def test_registry_executes_read_text_with_truncation_hint(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("line-1\nline-2\nline-3\nline-4\n", encoding="utf-8")
    registry = ToolRegistry(
        context=ToolContext.create(
            repo_root=tmp_path,
            safety_config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
        )
    )
    registry.register(ReadTool())

    result = registry.execute("read", {"path": "note.txt", "offset": 1, "limit": 4})

    assert result["truncated"] is True
    assert result["next_offset"] == 3
    text_part = result["content"][0]
    assert text_part == {
        "type": "text",
        "text": "line-1\nline-2\n\n[Showing lines 1-2 of 4. Use offset=3 to continue.]",
    }
    assert result["details"]["truncation"]["truncatedBy"] == "lines"


def test_read_image_parts_survive_tool_result_content_rewrite(tmp_path: Path) -> None:
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWkAAAAASUVORK5CYII="
    )
    (tmp_path / "pixel.png").write_bytes(image_bytes)
    hooks = HookRegistry()

    async def rewrite_tool_result(event, ctx):
        del ctx
        return {"content": event["output"]["content"]}

    hooks.on("tool_result", rewrite_tool_result, priority=100)
    registry = ToolRegistry(
        context=ToolContext.create(repo_root=tmp_path),
        hook_runner=HookRunner(registry=hooks),
    )
    registry.register(ReadTool())

    result = registry.execute(
        "read",
        {"path": "pixel.png"},
        hook_context=HookContext(session_id="sess-read-list", repo_root=tmp_path),
    )

    assert set(result.keys()) == {"content"}
    assert isinstance(result["content"], list)
    assert result["content"][0] == {"type": "text", "text": "Image: pixel.png (image/png, 68 bytes)"}
    assert result["content"][1]["type"] == "image"
    assert result["content"][1]["mime_type"] == "image/png"
    assert result["content"][1]["image_url"].startswith("data:image/png;base64,")
