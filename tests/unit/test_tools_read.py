"""Unit tests for ReadTool: segmented reads, truncation, image support, serialize_result, dedup."""

from pathlib import Path
import base64

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.safety import ToolSafety
from agent.platform.tools.safety import ToolSafetyConfig
from agent.core.tools.base import set_tool_safety_factory, set_tool_safety_config_factory
from agent.core.tools.session_file_state import SessionFileState

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def _context_with_state(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> tuple[ToolContext, SessionFileState]:
    base = ToolContext.create(repo_root=tmp_path, safety_config=config)
    state = SessionFileState()
    ctx = base.with_session("test-session", session_file_state=state)
    return ctx, state


def test_read_supports_segmented_reads(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 7))
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": "note.txt", "offset": 3, "limit": 2}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "line-3\nline-4"
    assert result["truncated"] is False
    assert result["next_offset"] is None


def test_read_truncates_output_by_lines(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 7))
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 5}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "line-1\nline-2"
    assert result["truncated"] is True
    assert result["next_offset"] is None
    assert result["details"]["truncation"]["truncatedBy"] == "lines"


def test_read_truncates_by_bytes(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("1234567890\nabcdefghij\nline-3", encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=200, read_max_bytes=16),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 3}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "1234567890"
    assert result["truncated"] is True
    assert result["next_offset"] is None
    assert result["details"]["truncation"]["truncatedBy"] == "bytes"


def test_read_offset_out_of_range_surfaces_details(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("line-1\nline-2", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="offset is out of range") as exc_info:
        ReadTool().run({"path": "note.txt", "offset": 3}, ctx)

    assert exc_info.value.details["offset"] == 3
    assert exc_info.value.details["total_lines"] == 2


def test_read_allows_path_outside_repo(tmp_path: Path) -> None:
    # bugfix-355: Read no longer hard-errors on paths outside repo sandbox.
    # Boundary enforcement moved to auto_mode_gate hook (classifier / ask flow).
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("allowed content", encoding="utf-8")
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": str(outside)}, ctx)

    assert "content" in result
    serialized = ReadTool().serialize_result(result)
    assert "allowed content" in serialized


def test_read_allows_codex_home_skills_outside_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # bugfix-355: All paths outside repo are allowed now (no special CODEX_HOME case needed).
    # This test retained to verify reading from arbitrary external paths works.
    codex_home = tmp_path.parent / "codex-home"
    skill_file = codex_home / "skills" / "demo-skill" / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("# Demo\nuse this skill\n", encoding="utf-8")
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": str(skill_file)}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"].startswith("# Demo")
    assert result["path"] == str(skill_file)


def test_read_returns_text_and_image_parts_for_png(tmp_path: Path) -> None:
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWkAAAAASUVORK5CYII="
    )
    (tmp_path / "pixel.png").write_bytes(image_bytes)
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": "pixel.png"}, ctx)

    assert result["truncated"] is False
    assert result["next_offset"] is None
    assert isinstance(result["content"], list)
    assert result["content"][0]["type"] == "text"
    assert result["content"][0]["text"].startswith("Read image file [image/png]")
    assert "original 1x1" in result["content"][0]["text"]
    assert "displayed at 1x1" in result["content"][0]["text"]
    image_part = result["content"][1]
    assert image_part["type"] == "image"
    assert image_part["mimeType"] == "image/png"
    assert image_part["data"] == base64.b64encode(image_bytes).decode("ascii")


def test_read_truncation_returns_truncated_content(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 6))
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 5}, ctx)

    assert result["truncated"] is True
    assert result["next_offset"] is None
    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "line-1\nline-2"


def test_read_serialize_result_adds_line_numbers() -> None:
    tool = ReadTool()
    output = {
        "path": "test.py",
        "offset": 3,
        "next_offset": None,
        "total_lines": 5,
        "truncated": False,
        "content": [{"type": "text", "text": "line-3\nline-4\nline-5"}],
    }
    result = tool.serialize_result(output)
    assert result == "     3→line-3\n     4→line-4\n     5→line-5"


def test_read_serialize_result_skips_line_numbers_for_file_unchanged() -> None:
    tool = ReadTool()
    output = {"type": "file_unchanged", "file": {"filePath": "test.py"}}
    result = tool.serialize_result(output)
    assert "File unchanged since last read" in result
    assert "→" not in result


def test_read_serialize_result_returns_blocks_for_images() -> None:
    tool = ReadTool()
    output = {
        "path": "img.png",
        "offset": 1,
        "next_offset": None,
        "total_lines": 0,
        "truncated": False,
        "content": [
            {"type": "text", "text": "Read image file [image/png]"},
            {"type": "image", "data": "abc", "mimeType": "image/png"},
        ],
    }
    result = tool.serialize_result(output)
    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert result[0]["text"] == "Read image file [image/png]"
    assert result[1]["type"] == "image"
    assert result[1]["data"] == "abc"
    assert result[1]["mimeType"] == "image/png"


def test_read_serialize_result_returns_empty_file_warning() -> None:
    tool = ReadTool()
    output = {
        "path": "empty.txt",
        "offset": 1,
        "next_offset": None,
        "total_lines": 0,
        "truncated": False,
        "content": [{"type": "text", "text": ""}],
    }
    result = tool.serialize_result(output)
    assert "<system-reminder>" in result
    assert "contents are empty" in result


def test_add_line_numbers_formats_six_digit_line_without_padding() -> None:
    from agent.platform.tools.builtins.read import _format_line_number

    assert _format_line_number(1, "hello") == "     1→hello"
    assert _format_line_number(10, "world") == "    10→world"
    assert _format_line_number(999999, "x") == "999999→x"
    assert _format_line_number(1000000, "y") == "1000000→y"


def test_add_line_numbers_preserves_empty_text() -> None:
    from agent.platform.tools.builtins.read import _add_line_numbers

    assert _add_line_numbers("") == ""


def test_add_line_numbers_handles_crlf() -> None:
    from agent.platform.tools.builtins.read import _add_line_numbers

    result = _add_line_numbers("a\r\nb\r\nc", start_line=1)
    assert result == "     1→a\n     2→b\n     3→c"


class TestReadDedup:
    def test_returns_file_unchanged_on_exact_range_match(self, tmp_path: Path) -> None:
        (tmp_path / "note.txt").write_text("line-1\nline-2\nline-3\n", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        # First read
        result1 = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 2}, ctx)
        assert result1.get("type") != "file_unchanged"

        # Second read with same range
        result2 = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 2}, ctx)
        assert result2["type"] == "file_unchanged"

    def test_re_reads_when_range_differs(self, tmp_path: Path) -> None:
        (tmp_path / "note.txt").write_text("line-1\nline-2\nline-3\n", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        ReadTool().run({"path": "note.txt", "offset": 1, "limit": 2}, ctx)
        result = ReadTool().run({"path": "note.txt", "offset": 3, "limit": 1}, ctx)

        assert result.get("type") != "file_unchanged"
        assert result["content"][0]["text"] == "line-3"

    def test_re_reads_after_external_modification(self, tmp_path: Path) -> None:
        (tmp_path / "note.txt").write_text("line-1\nline-2\n", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        ReadTool().run({"path": "note.txt"}, ctx)
        (tmp_path / "note.txt").write_text("changed\n", encoding="utf-8")
        result = ReadTool().run({"path": "note.txt"}, ctx)

        assert result.get("type") != "file_unchanged"
        assert result["content"][0]["text"] == "changed"
