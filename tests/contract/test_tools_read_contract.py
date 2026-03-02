from pathlib import Path
import base64

from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.read import ReadTool
from nano_multiagent.tools.safety import ToolSafetyConfig


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def test_read_image_contract_returns_text_plus_image_parts(tmp_path: Path) -> None:
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWkAAAAASUVORK5CYII="
    )
    (tmp_path / "pixel.png").write_bytes(image_bytes)
    result = ReadTool().run({"path": "pixel.png"}, _context(tmp_path))

    assert set(result.keys()) == {"path", "offset", "next_offset", "total_lines", "truncated", "content"}
    assert isinstance(result["content"], list)
    assert result["content"][0]["type"] == "text"
    assert result["content"][1]["type"] == "image"
    assert result["content"][1]["mime_type"] == "image/png"
    assert result["content"][1]["image_url"].startswith("data:image/png;base64,")


def test_read_truncation_contract_contains_next_offset_hint(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("a\nb\nc\nd\n", encoding="utf-8")
    result = ReadTool().run(
        {"path": "note.txt", "offset": 1, "limit": 4},
        _context(tmp_path, config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024)),
    )

    assert result["truncated"] is True
    assert result["next_offset"] == 3
    assert isinstance(result["content"], str)
    assert "offset=3" in result["content"]
