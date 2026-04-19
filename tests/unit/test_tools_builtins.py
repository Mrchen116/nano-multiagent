from pathlib import Path
import base64

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.builtins.task import TaskTool
from agent.platform.tools.builtins.write import WriteTool
from agent.platform.tools.constants import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_KILOBYTES,
    DEFAULT_MAX_LINES,
)
from agent.platform.tools.safety import CommandExecution
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


def test_builtin_tool_descriptions_align_with_tool_design_doc() -> None:
    assert ReadTool.description == (
        "Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
        f"Images are sent as attachments. For text files, output is truncated to {DEFAULT_MAX_LINES} "
        f"lines or {DEFAULT_MAX_KILOBYTES}KB (whichever is hit first). Use offset/limit for large "
        "files. When you need the full file, continue with offset until complete. "
        "Results are returned using cat -n format, with line numbers starting at 1."
    )
    assert BashTool.description == (
        "Execute a bash command in the current working directory. Returns stdout and stderr. "
        f"Output is truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_KILOBYTES}KB "
        "(whichever is hit first). If truncated, full output is saved to a temp file. Optionally "
        "provide a timeout in seconds."
    )
    assert EditTool.description == (
        "Edit a file by replacing exact text. The oldText must match exactly (including whitespace). "
        "Use this for precise, surgical edits. "
        "When editing text from Read tool output, ensure you preserve the exact indentation "
        "(tabs/spaces) as it appears AFTER the line number prefix. "
        "The line number prefix format is: 6 spaces + line number + →. "
        "Everything after that is the actual file content to match. "
        "Never include any part of the line number prefix in the oldText or newText."
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
    assert result["type"] == "update"
    assert result["displayPath"] == "notes/todo.txt"


def test_edit_replaces_exact_text_once(tmp_path: Path) -> None:
    target = tmp_path / "config.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    ctx = _context(tmp_path)

    result = EditTool().run(
        {"path": "config.txt", "oldText": "beta", "newText": "BETA"},
        ctx,
    )

    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert result["displayPath"] == "config.txt"
    assert result["replaceAll"] is False
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
    assert "stdout" in result
    assert isinstance(result["fullOutputPath"], str)
    full_output_path = result["fullOutputPath"]
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
    assert result["stdout"] == "ok"
    assert result["exitCode"] == 0


def test_bash_success_merges_stdout_and_stderr_into_stdout(tmp_path: Path) -> None:
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

    assert result["stdout"]
    assert "out-1" in result["stdout"]
    assert "err-1" in result["stdout"]
    assert "out-2" in result["stdout"]
    assert "stderr" in result


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


def test_write_serialize_result_create() -> None:
    tool = WriteTool()
    output = {"type": "create", "filePath": "/tmp/foo.py", "displayPath": "foo.py"}
    result = tool.serialize_result(output)
    assert result == "File created successfully at: foo.py"


def test_write_serialize_result_update() -> None:
    tool = WriteTool()
    output = {"type": "update", "filePath": "/tmp/bar.py", "displayPath": "bar.py"}
    result = tool.serialize_result(output)
    assert result == "The file bar.py has been updated successfully."


def test_write_serialize_result_fallback_for_unknown_type() -> None:
    tool = WriteTool()
    output = {"type": "unknown", "filePath": "/tmp/baz.py", "displayPath": "baz.py"}
    result = tool.serialize_result(output)
    import json
    assert json.loads(result) == output


def test_write_creates_new_file(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    result = WriteTool().run({"path": "newfile.txt", "content": "hello"}, ctx)
    assert result["type"] == "create"
    assert result["displayPath"] == "newfile.txt"
    assert (tmp_path / "newfile.txt").read_text(encoding="utf-8") == "hello"


def test_edit_serialize_result_success() -> None:
    tool = EditTool()
    output = {"filePath": "/tmp/foo.py", "displayPath": "foo.py", "replaceAll": False}
    result = tool.serialize_result(output)
    assert result == "The file foo.py has been updated successfully."


def test_edit_serialize_result_replace_all() -> None:
    tool = EditTool()
    output = {"filePath": "/tmp/bar.py", "displayPath": "bar.py", "replaceAll": True}
    result = tool.serialize_result(output)
    assert result == (
        "The file bar.py has been updated. "
        "All occurrences were successfully replaced."
    )


def test_edit_serialize_result_error() -> None:
    tool = EditTool()
    result = tool.serialize_result(None, error="file does not exist")
    assert result == "file does not exist"


def test_edit_serialize_result_fallback() -> None:
    tool = EditTool()
    result = tool.serialize_result("unexpected string")
    assert result == '"unexpected string"'


def test_bash_serialize_result_success() -> None:
    tool = BashTool()
    output = {"stdout": "line-1\nline-2", "exitCode": 0, "truncated": False}
    result = tool.serialize_result(output)
    assert result == "line-1\nline-2"


def test_bash_serialize_result_empty() -> None:
    tool = BashTool()
    output = {"stdout": "", "exitCode": 0, "truncated": False}
    result = tool.serialize_result(output)
    assert result == "(no output)"


def test_bash_serialize_result_truncated() -> None:
    tool = BashTool()
    output = {
        "stdout": "line-4\nline-5\nline-6",
        "exitCode": 0,
        "truncated": True,
        "fullOutputPath": "/tmp/bash-output-xxx.log",
    }
    result = tool.serialize_result(output)
    assert "(Output truncated." in result
    assert "/tmp/bash-output-xxx.log" in result


def test_bash_serialize_result_strips_leading_newlines() -> None:
    tool = BashTool()
    output = {"stdout": "\n\nhello", "exitCode": 0, "truncated": False}
    result = tool.serialize_result(output)
    assert result == "hello"


def test_bash_serialize_result_error() -> None:
    tool = BashTool()
    result = tool.serialize_result(None, error="Command timed out")
    assert result == "Command timed out"


# ---------------------------------------------------------------------------
# TaskTool.serialize_result
# ---------------------------------------------------------------------------


def test_task_serialize_result_completed() -> None:
    tool = TaskTool()
    output = {
        "status": "completed",
        "content": "task output",
        "sessionId": "sess_1",
        "durationMs": 123,
        "agent": "oracle",
        "continuation": False,
        "taskId": "tid_1",
    }
    result = tool.serialize_result(output)
    assert result.startswith("Task completed in 123ms.")
    assert "Agent: oracle" in result
    assert "task output" in result
    assert "session_id: sess_1" in result
    assert "task_id: tid_1" in result


def test_task_serialize_result_continuation() -> None:
    tool = TaskTool()
    output = {
        "status": "completed",
        "content": "continued output",
        "sessionId": "sess_2",
        "durationMs": 456,
        "agent": "explore",
        "continuation": True,
        "taskId": "tid_2",
    }
    result = tool.serialize_result(output)
    assert result.startswith("Task continued and completed in 456ms.")
    assert "continued output" in result
    assert "session_id: sess_2" in result


def test_task_serialize_result_empty_content() -> None:
    tool = TaskTool()
    output = {
        "status": "completed",
        "content": "",
        "sessionId": "sess_3",
        "durationMs": 10,
        "agent": "test",
        "continuation": False,
        "taskId": "tid_3",
    }
    result = tool.serialize_result(output)
    assert "(Subagent completed but returned no output.)" in result


def test_task_serialize_result_async_launched() -> None:
    tool = TaskTool()
    output = {
        "status": "async_launched",
        "taskId": "tid_4",
        "sessionId": "sess_4",
        "description": "research",
        "agent": "research (category: research)",
        "continuation": False,
    }
    result = tool.serialize_result(output)
    assert result.startswith("Background task launched.")
    assert "Task ID: tid_4" in result
    assert "Description: research" in result
    assert "Agent: research (category: research)" in result
    assert "Status: queued" in result


def test_task_serialize_result_async_continued() -> None:
    tool = TaskTool()
    output = {
        "status": "async_launched",
        "taskId": "tid_5",
        "sessionId": "sess_5",
        "description": "follow-up",
        "agent": "oracle",
        "continuation": True,
    }
    result = tool.serialize_result(output)
    assert result.startswith("Background task continued.")
    assert "Agent continues with full previous context preserved." in result


def test_task_serialize_result_failed() -> None:
    tool = TaskTool()
    output = {
        "status": "failed",
        "title": "Task failed",
        "error": "something broke",
        "sessionId": "sess_6",
    }
    result = tool.serialize_result(output)
    assert result.startswith("Task failed")
    assert "Error: something broke" in result
    assert "session_id: sess_6" in result


def test_task_serialize_result_error_passthrough() -> None:
    tool = TaskTool()
    result = tool.serialize_result(None, error="tool execution aborted")
    assert result == "tool execution aborted"


def test_task_serialize_result_non_mapping_fallback() -> None:
    tool = TaskTool()
    result = tool.serialize_result("plain string")
    assert result == "plain string"


# ---------------------------------------------------------------------------
# SessionFileState / Read-Before-Write tests
# ---------------------------------------------------------------------------

class TestWriteReadBeforeWrite:
    def test_rejects_overwrite_when_file_never_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        with pytest.raises(ToolError) as exc_info:
            WriteTool().run({"path": "existing.txt", "content": "new"}, ctx)

        assert exc_info.value.details.get("errorCode") == 6
        assert "has not been read yet" in str(exc_info.value)

    def test_rejects_overwrite_when_file_stale(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
        ctx, state = _context_with_state(tmp_path)
        stat = (tmp_path / "existing.txt").stat()
        state.record_read(str(tmp_path / "existing.txt"), stat.st_mtime_ns, stat.st_size, offset=1, limit=None)

        # Simulate external modification
        (tmp_path / "existing.txt").write_text("externally changed", encoding="utf-8")

        with pytest.raises(ToolError) as exc_info:
            WriteTool().run({"path": "existing.txt", "content": "new"}, ctx)

        assert exc_info.value.details.get("errorCode") == 7
        assert "modified externally" in str(exc_info.value)

    def test_allows_create_without_read(self, tmp_path: Path) -> None:
        ctx, _state = _context_with_state(tmp_path)

        result = WriteTool().run({"path": "newfile.txt", "content": "hello"}, ctx)

        assert result["type"] == "create"

    def test_allows_overwrite_after_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
        ctx, state = _context_with_state(tmp_path)
        # Simulate prior read
        ReadTool().run({"path": "existing.txt"}, ctx)

        result = WriteTool().run({"path": "existing.txt", "content": "new"}, ctx)

        assert result["type"] == "update"
        assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "new"

    def test_allows_second_write_after_first(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("v1", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)
        ReadTool().run({"path": "existing.txt"}, ctx)
        WriteTool().run({"path": "existing.txt", "content": "v2"}, ctx)

        # Second write should succeed because first write updated the state.
        result = WriteTool().run({"path": "existing.txt", "content": "v3"}, ctx)
        assert result["type"] == "update"


class TestEditReadBeforeWrite:
    def test_rejects_edit_when_file_never_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)

        with pytest.raises(ToolError) as exc_info:
            EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        assert exc_info.value.details.get("errorCode") == 6
        assert "has not been read yet" in str(exc_info.value)

    def test_rejects_edit_when_file_stale(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, state = _context_with_state(tmp_path)
        stat = (tmp_path / "existing.txt").stat()
        state.record_read(str(tmp_path / "existing.txt"), stat.st_mtime_ns, stat.st_size, offset=1, limit=None)

        (tmp_path / "existing.txt").write_text("externally changed", encoding="utf-8")

        with pytest.raises(ToolError) as exc_info:
            EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        assert exc_info.value.details.get("errorCode") == 7
        assert "modified externally" in str(exc_info.value)

    def test_allows_edit_after_read(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)
        ReadTool().run({"path": "existing.txt"}, ctx)

        result = EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        assert result["displayPath"] == "existing.txt"
        assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "hi world"

    def test_allows_second_edit_after_first(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("hello world", encoding="utf-8")
        ctx, _state = _context_with_state(tmp_path)
        ReadTool().run({"path": "existing.txt"}, ctx)
        EditTool().run({"path": "existing.txt", "oldText": "hello", "newText": "hi"}, ctx)

        # Second edit should succeed because first edit updated the state.
        result = EditTool().run({"path": "existing.txt", "oldText": "hi", "newText": "hey"}, ctx)
        assert result["displayPath"] == "existing.txt"


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

