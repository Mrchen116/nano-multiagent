from pathlib import Path
import base64

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.safety import ToolSafetyConfig


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def test_read_image_contract_returns_text_plus_image_parts(tmp_path: Path) -> None:
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWkAAAAASUVORK5CYII="
    )
    (tmp_path / "pixel.png").write_bytes(image_bytes)
    result = ReadTool().run({"path": "pixel.png"}, _context(tmp_path))

    assert set(result.keys()) == {
        "path",
        "offset",
        "next_offset",
        "total_lines",
        "truncated",
        "content",
    }
    assert isinstance(result["content"], list)
    assert result["content"][0]["type"] == "text"
    assert result["content"][0]["text"].startswith("Read image file [image/png]")
    assert "original 1x1" in result["content"][0]["text"]
    assert result["content"][1]["type"] == "image"
    assert result["content"][1] == {
        "type": "image",
        "mimeType": "image/png",
        "data": base64.b64encode(image_bytes).decode("ascii"),
    }


def test_read_over_limit_contract_returns_actionable_error(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("x" * 58797, encoding="utf-8")
    with pytest.raises(ToolError, match="exceeds maximum allowed size") as error:
        ReadTool().run(
            {"path": "note.txt", "offset": 1, "limit": 1}, _context(tmp_path)
        )
    assert error.value.details["tool_name"] == "read"
    assert "offset and limit" in str(error.value)
    assert "search" in str(error.value)


def test_read_offset_out_of_range_contract_includes_details(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("line-1\nline-2", encoding="utf-8")

    with pytest.raises(ToolError, match="offset is out of range") as exc_info:
        ReadTool().run({"path": "note.txt", "offset": 3}, _context(tmp_path))

    assert exc_info.value.details["offset"] == 3
    assert exc_info.value.details["total_lines"] == 2
