from pathlib import Path
import base64

import pytest

from nano_multiagent.core.errors import ToolError
from nano_multiagent.platform.tools.base import ToolContext
from nano_multiagent.platform.tools.builtins.bash import BashTool
from nano_multiagent.platform.tools.builtins.edit import EditTool
from nano_multiagent.platform.tools.builtins.read import ReadTool
from nano_multiagent.platform.tools.builtins.task import TaskTool
from nano_multiagent.platform.tools.builtins.write import WriteTool
from nano_multiagent.platform.tools.constants import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_KILOBYTES,
    DEFAULT_MAX_LINES,
)
from nano_multiagent.platform.tools.safety import CommandExecution
from nano_multiagent.platform.tools.safety import ToolSafety
from nano_multiagent.platform.tools.safety import ToolSafetyConfig


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def test_builtin_tool_descriptions_align_with_tool_design_doc() -> None:
    assert ReadTool.description == (
        "Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
        f"Images are sent as attachments. For text files, output is truncated to {DEFAULT_MAX_LINES} "
        f"lines or {DEFAULT_MAX_KILOBYTES}KB (whichever is hit first). Use offset/limit for large "
        "files. When you need the full file, continue with offset until complete."
    )
    assert BashTool.description == (
        "Execute a bash command in the current working directory. Returns stdout and stderr. "
        f"Output is truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_KILOBYTES}KB "
        "(whichever is hit first). If truncated, full output is saved to a temp file. Optionally "
        "provide a timeout in seconds."
    )
    assert EditTool.description == (
        "Edit a file by replacing exact text. The oldText must match exactly (including whitespace). "
        "Use this for precise, surgical edits."
    )
    assert WriteTool.description == (
        "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
        "Automatically creates parent directories."
    )
    assert TaskTool.description == (
        "Spawn agent task with category-based or direct agent selection.\n\n"
        "MUTUALLY EXCLUSIVE: Provide EITHER category OR subagent_type, not both (unless continuing a session).\n\n"
        "- load_skills: ALWAYS REQUIRED. Pass at least one skill name (e.g., [\"playwright\"], [\"git-master\", \"frontend-ui-ux\"]).\n"
        "- category: Use predefined category → Spawns Sisyphus-Junior with category config\n"
        "  Available categories:\n"
        "${categoryList}\n"
        "- subagent_type: Use specific agent directly (e.g., \"oracle\", \"explore\")\n"
        "- run_in_background: true=async (returns task_id), false=sync (waits for result). Default: false. "
        "Use background=true ONLY for parallel exploration with 5+ independent queries.\n"
        "- session_id: Existing Task session to continue (from previous task output). Continues agent with FULL CONTEXT PRESERVED - "
        "saves tokens, maintains continuity.\n"
        "- command: The command that triggered this task (optional, for slash command tracking).\n\n"
        "**WHEN TO USE session_id:**\n"
        "- Task failed/incomplete → session_id with \"fix: [specific issue]\"\n"
        "- Need follow-up on previous result → session_id with additional question\n"
        "- Multi-turn conversation with same agent → always session_id instead of new task\n\n"
        "Prompts MUST be in English."
    )


def test_builtin_tool_parameter_descriptions_align_with_tool_design_doc() -> None:
    read_properties = ReadTool.input_schema["properties"]
    assert read_properties["path"]["description"] == "Path to the file to read (relative or absolute)"
    assert read_properties["offset"]["description"] == "Line number to start reading from (1-indexed)"
    assert read_properties["limit"]["description"] == "Maximum number of lines to read"

    bash_properties = BashTool.input_schema["properties"]
    assert bash_properties["command"]["description"] == "Bash command to execute"
    assert bash_properties["timeout"]["description"] == "Timeout in seconds (optional, no default timeout)"

    edit_properties = EditTool.input_schema["properties"]
    assert edit_properties["path"]["description"] == "Path to the file to edit (relative or absolute)"
    assert edit_properties["oldText"]["description"] == "Exact text to find and replace (must match exactly)"
    assert edit_properties["newText"]["description"] == "New text to replace the old text with"

    write_properties = WriteTool.input_schema["properties"]
    assert write_properties["path"]["description"] == "Path to the file to write (relative or absolute)"
    assert write_properties["content"]["description"] == "Content to write to the file"

    task_properties = TaskTool.input_schema["properties"]
    assert task_properties["load_skills"]["description"] == (
        "Skill names to inject. REQUIRED - pass [] if no skills needed, but IT IS HIGHLY RECOMMENDED to pass "
        "proper skills like [\"playwright\"], [\"git-master\"] for best results."
    )
    assert task_properties["description"]["description"] == "Short task description (3-5 words)"
    assert task_properties["prompt"]["description"] == "Full detailed prompt for the agent"
    assert task_properties["run_in_background"]["description"] == "true=async (returns task_id), false=sync (waits). Default: false"
    assert task_properties["category"]["description"] == (
        "Category (e.g., ${categoryExamples}). Mutually exclusive with subagent_type."
    )
    assert task_properties["subagent_type"]["description"] == (
        "Agent name (e.g., 'oracle', 'explore'). Mutually exclusive with category."
    )
    assert task_properties["session_id"]["description"] == "Existing Task session to continue"
    assert task_properties["command"]["description"] == "The command that triggered this task"


def test_tool_safety_default_limits_follow_shared_tool_constants() -> None:
    config = ToolSafetyConfig()

    assert config.read_max_lines == DEFAULT_MAX_LINES
    assert config.bash_max_output_lines == DEFAULT_MAX_LINES
    assert config.read_max_bytes == DEFAULT_MAX_BYTES
    assert config.bash_max_output_bytes == DEFAULT_MAX_BYTES


def test_read_supports_segmented_reads(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 7))
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(tmp_path)

    result = ReadTool().run({"path": "note.txt", "offset": 3, "limit": 2}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "line-3\nline-4\n\n[2 more lines in file. Use offset=5 to continue.]"
    assert result["truncated"] is False
    assert result["next_offset"] == 5


def test_read_truncates_output_and_reports_next_offset(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 7))
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 5}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "line-1\nline-2\n\n[Showing lines 1-2 of 6. Use offset=3 to continue.]"
    assert result["truncated"] is True
    assert result["next_offset"] == 3
    assert result["details"]["truncation"]["truncatedBy"] == "lines"


def test_read_truncates_by_bytes_and_reports_limit_hint(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("1234567890\nabcdefghij\nline-3", encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=200, read_max_bytes=16),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 3}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "1234567890\n\n[Showing lines 1-1 of 3 (16B limit). Use offset=2 to continue.]"
    assert result["truncated"] is True
    assert result["next_offset"] == 2
    assert result["details"]["truncation"]["truncatedBy"] == "bytes"


def test_read_first_line_exceeds_byte_limit_returns_bash_hint(tmp_path: Path) -> None:
    (tmp_path / "oversized.txt").write_text(f"{'a' * 11}\nline-2", encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=200, read_max_bytes=10),
    )

    result = ReadTool().run({"path": "oversized.txt", "offset": 1}, ctx)

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert (
        text_part["text"]
        == "[Line 1 is 11B, exceeds 10B limit. Use bash: sed -n '1p' oversized.txt | head -c 10]"
    )
    assert result["truncated"] is True
    assert result["details"]["truncation"]["firstLineExceedsLimit"] is True


def test_read_offset_out_of_range_surfaces_details(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("line-1\nline-2", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="offset is out of range") as exc_info:
        ReadTool().run({"path": "note.txt", "offset": 3}, ctx)

    assert exc_info.value.details["offset"] == 3
    assert exc_info.value.details["total_lines"] == 2


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

    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"].startswith("# Demo")
    assert result["path"] == str(skill_file)


def test_write_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "notes" / "todo.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before", encoding="utf-8")
    ctx = _context(tmp_path)

    result = WriteTool().run({"path": "notes/todo.txt", "content": "after"}, ctx)

    assert target.read_text(encoding="utf-8") == "after"
    assert result["content"] == [{"type": "text", "text": "Successfully wrote 5 bytes to notes/todo.txt"}]


def test_edit_replaces_exact_text_once(tmp_path: Path) -> None:
    target = tmp_path / "config.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    ctx = _context(tmp_path)

    result = EditTool().run(
        {"path": "config.txt", "oldText": "beta", "newText": "BETA"},
        ctx,
    )

    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert result["content"] == [{"type": "text", "text": "Successfully replaced text in config.txt."}]
    assert result["details"]["firstChangedLine"] == 2
    assert "--- a/config.txt" in result["details"]["diff"]
    assert "+++ b/config.txt" in result["details"]["diff"]
    assert "-beta" in result["details"]["diff"]
    assert "+BETA" in result["details"]["diff"]


def test_edit_fails_on_multiple_matches(tmp_path: Path) -> None:
    target = tmp_path / "dup.txt"
    target.write_text("x\nx\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="text must be unique"):
        EditTool().run({"path": "dup.txt", "oldText": "x", "newText": "y"}, ctx)


def test_edit_fails_when_old_text_not_found(tmp_path: Path) -> None:
    target = tmp_path / "missing.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="Could not find the exact text"):
        EditTool().run({"path": "missing.txt", "oldText": "gamma", "newText": "GAMMA"}, ctx)


def test_edit_fails_when_replacement_makes_no_change(tmp_path: Path) -> None:
    target = tmp_path / "same.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="No changes made"):
        EditTool().run({"path": "same.txt", "oldText": "beta", "newText": "beta"}, ctx)


def test_bash_reports_non_zero_exit(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        BashTool().run({"command": "python -c \"import sys;sys.exit(7)\""}, ctx)

    assert str(exc_info.value).endswith("Command exited with code 7")
    assert exc_info.value.details["exitCode"] == 7
    assert exc_info.value.details["tool_name"] == "bash"
    assert "content" in exc_info.value.details


def test_bash_handles_timeout(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(ToolError, match="Command timed out after 0.05 seconds") as exc_info:
        BashTool().run(
            {
                "command": (
                    "python -c \"import time; "
                    "print('before-timeout', flush=True); "
                    "time.sleep(0.3)\""
                ),
                "timeout": 0.05,
            },
            ctx,
        )
    assert exc_info.value.details["timedOut"] is True
    assert exc_info.value.details["timeout"] == 0.05
    assert exc_info.value.details["tool_name"] == "bash"
    assert isinstance(exc_info.value.details["content"], str)


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
    assert "Showing lines" in result["content"]
    assert "Full output:" in result["content"]
    full_output_path = result["fullOutputPath"]
    assert full_output_path in result["content"]
    assert isinstance(full_output_path, str)
    content = Path(full_output_path).read_text(encoding="utf-8")
    assert "line-0" in content
    assert "line-5" in content


def test_bash_without_timeout_does_not_inject_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run_command_stream(  # noqa: ANN202
        self,  # noqa: ANN001
        *,
        command: str,
        cwd: Path,
        timeout: float | None,
        tool_name: str,
        allow_unlisted: bool = False,
        on_event=None,  # noqa: ANN001,ARG001
        heartbeat_interval: float = 0.5,  # noqa: ARG001
    ) -> CommandExecution:
        del self, command, cwd, tool_name, allow_unlisted
        captured["timeout"] = timeout
        return CommandExecution(exit_code=0, text="ok", truncated=False)

    monkeypatch.setattr(ToolSafety, "run_command_stream", fake_run_command_stream)
    ctx = _context(tmp_path)

    result = BashTool().run({"command": "python -c \"print('ok')\""}, ctx)

    assert captured["timeout"] is None
    assert result["content"] == "ok"
    assert result["exitCode"] == 0


def test_bash_success_merges_stdout_and_stderr_into_content(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    result = BashTool().run(
        {
            "command": (
                "python -c \"import sys; "
                "print('out-1'); "
                "sys.stderr.write('err-1\\\\n'); "
                "print('out-2')\""
            )
        },
        ctx,
    )

    assert result["content"]
    assert "out-1" in result["content"]
    assert "err-1" in result["content"]
    assert "out-2" in result["content"]
    assert "stdout" not in result
    assert "stderr" not in result


def test_bash_aborted_contract_message_and_details(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    def fake_run_command_stream(**kwargs):  # noqa: ANN003
        del kwargs
        raise ToolError("keyboard interrupt", tool_name="bash", details={"aborted": True})

    monkeypatch.setattr(ctx.safety, "run_command_stream", fake_run_command_stream)

    with pytest.raises(ToolError, match="Command aborted") as exc_info:
        BashTool().run({"command": "python -c \"print('ignored')\""}, ctx)

    assert exc_info.value.details["aborted"] is True
    assert exc_info.value.details["tool_name"] == "bash"


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


def test_read_truncation_appends_next_offset_hint(tmp_path: Path) -> None:
    content = "\n".join(f"line-{idx}" for idx in range(1, 6))
    (tmp_path / "note.txt").write_text(content, encoding="utf-8")
    ctx = _context(
        tmp_path,
        config=ToolSafetyConfig(read_max_lines=2, read_max_bytes=1024),
    )

    result = ReadTool().run({"path": "note.txt", "offset": 1, "limit": 5}, ctx)

    assert result["truncated"] is True
    assert result["next_offset"] == 3
    text_part = result["content"][0]
    assert text_part["type"] == "text"
    assert text_part["text"] == "line-1\nline-2\n\n[Showing lines 1-2 of 5. Use offset=3 to continue.]"
