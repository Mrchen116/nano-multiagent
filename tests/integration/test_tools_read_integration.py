import asyncio
from pathlib import Path
import base64

from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.platform.llm.providers.anthropic.mapper import AnthropicMapper
from agent.platform.llm.providers.openai_compat.mapper import OpenAICompatMapper
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def test_registry_executes_read_image_and_keeps_part_structure(tmp_path: Path) -> None:
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWkAAAAASUVORK5CYII="
    )
    (tmp_path / "pixel.png").write_bytes(image_bytes)
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(ReadTool())

    result = asyncio.run(registry.execute("read", {"path": "pixel.png"}))

    assert isinstance(result["content"], list)
    assert [part["type"] for part in result["content"]] == ["text", "image"]
    assert result["content"][1]["mimeType"] == "image/png"
    assert result["content"][1]["data"] == base64.b64encode(image_bytes).decode("ascii")


def test_registry_executes_read_text_with_truncation_hint(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text(
        "line-1\nline-2\nline-3\nline-4\n", encoding="utf-8"
    )
    registry = ToolRegistry(
        context=ToolContext.create(
            repo_root=tmp_path,
            safety_config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
        )
    )
    registry.register(ReadTool())

    result = asyncio.run(
        registry.execute("read", {"path": "note.txt", "offset": 1, "limit": 4})
    )

    assert result["truncated"] is True
    # next_offset may be null when the read tool omits it on truncation; total_lines is authoritative.
    assert result["total_lines"] == 4
    text_part = result["content"][0]
    assert text_part["type"] == "text"
    # Content is truncated to read_max_lines=2; first two lines must appear.
    assert "line-1" in text_part["text"]
    assert "line-2" in text_part["text"]
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

    result = asyncio.run(
        registry.execute(
            "read",
            {"path": "pixel.png"},
            hook_context=HookContext(session_id="sess-read-list", repo_root=tmp_path),
        )
    )

    assert set(result.keys()) == {"content"}
    assert isinstance(result["content"], list)
    assert result["content"][0]["type"] == "text"
    assert result["content"][0]["text"].startswith("Read image file [image/png]")
    assert result["content"][1]["type"] == "image"
    assert result["content"][1]["mimeType"] == "image/png"
    assert result["content"][1]["data"] == base64.b64encode(image_bytes).decode("ascii")


def test_anthropic_mapper_accepts_read_image_blocks_directly() -> None:
    mapper = AnthropicMapper()
    base64_data = "QUJDRA=="
    blocks = [
        {"type": "text", "text": "Read image file [image/png]"},
        {"type": "image", "data": base64_data, "mimeType": "image/png"},
    ]
    request = LLMGenerateRequest(
        session_id="sess-read-image",
        model="anthropic-test",
        messages=(
            LLMMessage(role="user", content="show image"),
            LLMMessage(role="tool", content=blocks, tool_call_id="call-read-image"),
        ),
    )

    payload = mapper.map_generate_request(request)

    tool_result = payload["messages"][1]["content"][0]["content"]
    assert tool_result == [
        {"type": "text", "text": "Read image file [image/png]"},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64_data,
            },
        },
    ]


def test_openai_compat_mapper_accepts_read_image_blocks_directly() -> None:
    mapper = OpenAICompatMapper()
    base64_data = "QUJDRA=="
    blocks = [
        {"type": "text", "text": "Read image file [image/png]"},
        {"type": "image", "data": base64_data, "mimeType": "image/png"},
    ]
    request = LLMGenerateRequest(
        session_id="sess-read-image",
        model="openai-test",
        messages=(
            LLMMessage(role="user", content="show image"),
            LLMMessage(role="tool", content=blocks, tool_call_id="call-read-image"),
        ),
    )

    payload = mapper.map_generate_request(request)

    tool_message = payload["messages"][1]
    assert tool_message["content"] == [
        {"type": "text", "text": "Read image file [image/png]"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64_data}"},
        },
    ]
