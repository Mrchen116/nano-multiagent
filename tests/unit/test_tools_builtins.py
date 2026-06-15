"""Unit tests: builtin tool descriptions, parameter schemas, and safety constant alignment.

Execution, serialize_result, and file-state guard tests are split into:
- test_tools_read.py
- test_tools_write_edit.py
- test_tools_bash_task.py
"""

from pathlib import Path
import base64

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.bash import BashTool
from agent.platform.tools.builtins.edit import EditTool
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.builtins.write import WriteTool
from agent.platform.tools.constants import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_KILOBYTES,
    DEFAULT_MAX_LINES,
)
from agent.platform.tools.safety import CommandExecution
from agent.platform.tools.safety import ToolSafety
from agent.platform.tools.safety import ToolSafetyConfig
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.tools.session_file_state import SessionFileState

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _context(tmp_path: Path, *, config: ToolSafetyConfig | None = None) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path, safety_config=config)


def _context_with_state(
    tmp_path: Path, *, config: ToolSafetyConfig | None = None
) -> tuple[ToolContext, SessionFileState]:
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
        "Output larger than 30K chars is compressed by the result budget system. "
        "Optionally provide a timeout in seconds, or run in the background.\n\n"
        "- command: The bash command to execute.\n"
        "- description: Short description (3-5 words) for background task tracking.\n"
        "- timeout: Timeout in seconds for the command itself.\n"
        "- run_in_background: true=run in background (returns task_id immediately); "
        "false=wait for result. Default: false. Foreground commands auto-background after 15s."
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


def test_builtin_tool_parameter_descriptions_align_with_tool_design_doc() -> None:
    read_properties = ReadTool.input_schema["properties"]
    assert (
        read_properties["path"]["description"]
        == "Path to the file to read (relative or absolute)"
    )
    assert (
        read_properties["offset"]["description"]
        == "Line number to start reading from (1-indexed)"
    )
    assert read_properties["limit"]["description"] == "Maximum number of lines to read"

    bash_properties = BashTool.input_schema["properties"]
    assert bash_properties["command"]["description"] == "Bash command to execute"
    assert (
        bash_properties["description"]["description"]
        == "Short description for background task tracking (3-5 words)."
    )
    assert (
        bash_properties["timeout"]["description"]
        == "Timeout in seconds (optional, no default timeout)"
    )
    assert "run_in_background" in bash_properties

    edit_properties = EditTool.input_schema["properties"]
    assert (
        edit_properties["path"]["description"]
        == "Path to the file to edit (relative or absolute)"
    )
    assert (
        edit_properties["oldText"]["description"]
        == "Exact text to find and replace (must match exactly)"
    )
    assert (
        edit_properties["newText"]["description"]
        == "New text to replace the old text with"
    )

    write_properties = WriteTool.input_schema["properties"]
    assert (
        write_properties["path"]["description"]
        == "Path to the file to write (relative or absolute)"
    )
    assert write_properties["content"]["description"] == "Content to write to the file"


def test_tool_safety_default_limits_follow_shared_tool_constants() -> None:
    # After M6: ToolSafetyConfig only holds read budget; bash budget moved to BashRunnerConfig.
    from agent.platform.tools.builtins.bash_runner import BashRunnerConfig

    read_config = ToolSafetyConfig()
    assert read_config.read_max_lines == DEFAULT_MAX_LINES
    assert read_config.read_max_bytes == DEFAULT_MAX_BYTES

    bash_config = BashRunnerConfig()
    assert bash_config.bash_max_output_lines == DEFAULT_MAX_LINES
    assert bash_config.bash_max_output_bytes == DEFAULT_MAX_BYTES
