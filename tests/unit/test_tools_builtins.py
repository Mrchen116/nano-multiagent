from pathlib import Path
import base64

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.builtins.bash import BashTool
from nano_multiagent.tools.builtins.edit import EditTool
from nano_multiagent.tools.builtins.read import ReadTool
from nano_multiagent.tools.builtins.write import WriteTool
from nano_multiagent.tools.safety import ToolSafety
from nano_multiagent.tools.safety import ToolSafetyConfig


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def test_read_supports_segmented_reads(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 7)) + "\n"
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": "note.txt", "offset": 3, "limit": 2}, ctx)

    assert result["content"] == "line-3\nline-4"
    assert result["truncated"] is False
    assert result["next_offset"] == 5


def test_read_truncates_output_and_reports_next_offset(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 7)) + "\n"
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 5}, ctx)

    assert "line-1\nline-2" in result["content"]
    assert "offset=3" in result["content"]
    assert result["truncated"] is True
    assert result["next_offset"] == 3


def test_read_rejects_path_outside_repo(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("blocked", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="outside repo"):
        ReadTool().run({"path": "../outside.txt"}, ctx)


def test_read_allows_codex_home_skills_outside_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path.parent / "codex-home"
    skill_file = codex_home / "skills" / "demo-skill" / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("# Demo\nuse this skill\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": str(skill_file)}, ctx)

    assert result["content"].startswith("# Demo")
    assert result["path"] == str(skill_file)


def test_write_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "notes" / "todo.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before", encoding="utf-8")
    ctx = _context(tmp_path)

    result = WriteTool().run({"path": "notes/todo.txt", "content": "after"}, ctx)

    assert target.read_text(encoding="utf-8") == "after"
    assert result["bytes_written"] == len("after".encode("utf-8"))


def test_edit_replaces_exact_text_once(tmp_path: Path) -> None:
    target = tmp_path / "config.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    ctx = _context(tmp_path)

    result = EditTool().run(
        {"path": "config.txt", "oldText": "beta", "newText": "BETA"},
        ctx,
    )

    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert result["first_changed_line"] == 2


def test_edit_fails_on_multiple_matches(tmp_path: Path) -> None:
    target = tmp_path / "dup.txt"
    target.write_text("x\nx\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="multiple matches"):
        EditTool().run({"path": "dup.txt", "oldText": "x", "newText": "y"}, ctx)


def test_bash_reports_non_zero_exit(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        BashTool().run({"command": "python -c \"import sys;sys.exit(7)\""}, ctx)

    assert exc_info.value.details["exit_code"] == 7


def test_bash_handles_timeout(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="timed out"):
        BashTool().run({"command": "python -c \"import time;time.sleep(0.3)\"", "timeout": 0.05}, ctx)


def test_bash_rejects_disallowed_command(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="not allowed"):
        BashTool().run({"command": "rm -rf /tmp/forbidden"}, ctx)


def test_bash_truncates_large_output(tmp_path: Path) -> None:
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(bash_max_output_lines=3, bash_max_output_bytes=200),
    )

    result = BashTool().run(
        {"command": "python -c \"[print(f'line-{i}') for i in range(10)]\""},
        ctx,
    )

    assert result["truncated"] is True


def test_bash_truncation_returns_full_output_path(tmp_path: Path) -> None:
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(bash_max_output_lines=2, bash_max_output_bytes=200),
    )

    result = BashTool().run(
        {"command": "python -c \"[print(f'line-{i}') for i in range(6)]\""},
        ctx,
    )

    assert result["truncated"] is True
    full_output_path = result["full_output_path"]
    assert isinstance(full_output_path, str)
    content = Path(full_output_path).read_text(encoding="utf-8")
    assert "line-0" in content
    assert "line-5" in content


def test_bash_without_timeout_does_not_inject_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        del args
        captured["timeout"] = kwargs.get("timeout")

        class _Completed:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return _Completed()

    monkeypatch.setattr("subprocess.run", fake_run)
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())

    execution = safety.run_command(
        command="python -c \"print('ok')\"",
        cwd=tmp_path,
        timeout=None,
        tool_name="bash",
    )

    assert captured["timeout"] is None
    assert execution.stdout == "ok"
    assert execution.exit_code == 0


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
    assert "pixel.png" in result["content"][0]["text"]
    image_part = result["content"][1]
    assert image_part["type"] == "image"
    assert image_part["mime_type"] == "image/png"
    assert image_part["image_url"].startswith("data:image/png;base64,")


def test_read_truncation_appends_next_offset_hint(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 6)) + "\n"
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 5}, ctx)

    assert result["truncated"] is True
    assert result["next_offset"] == 3
    assert isinstance(result["content"], str)
    assert "line-1\nline-2" in result["content"]
    assert "offset=3" in result["content"]
