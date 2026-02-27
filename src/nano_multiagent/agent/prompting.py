import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from nano_multiagent.core.types import ToolSpec
from nano_multiagent.core.types import Message
from nano_multiagent.llm.interfaces import LLMMessage
from nano_multiagent.skills.formatter import format_available_skills_section
from nano_multiagent.skills.registry import SkillMetadata
from nano_multiagent.tools.builtins import builtin_tools

DEFAULT_SYSTEM_PROMPT = """You are an expert coding assistant operating inside a coding agent harness. You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
<RUNTIME_FILL:AVAILABLE_TOOLS>

In addition to the tools above, you may have access to other custom tools depending on the project.

Guidelines:
- Use bash for file operations like ls, rg, find
- Use read to examine files before editing. You must use this tool instead of cat or sed.
- Use edit for precise changes (old text must match exactly)
- Use write only for new files or complete rewrites
- When summarizing your actions, output plain text directly - do NOT use cat or bash to display what you did
- Be concise in your responses
- Show file paths clearly when working with files

<RUNTIME_FILL:SKILLS_SECTION>

Current date and time: <RUNTIME_FILL:CURRENT_DATETIME>
Current working directory: <RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>"""


def build_prompt_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    available_skills: Sequence[SkillMetadata] = (),
    available_tools: Sequence[ToolSpec] | None = None,
    current_datetime: datetime | None = None,
    current_working_directory: Path | None = None,
) -> tuple[LLMMessage, ...]:
    active_system_prompt = build_system_prompt(
        system_prompt=system_prompt,
        available_skills=available_skills,
        available_tools=available_tools,
        current_datetime=current_datetime,
        current_working_directory=current_working_directory,
    )
    messages: list[LLMMessage] = [LLMMessage(role="system", content=active_system_prompt)]
    for message in history_messages:
        messages.append(LLMMessage(role=message.role, content=message.content, name=message.name))
    messages.append(LLMMessage(role="user", content=user_text))
    return tuple(messages)


def build_system_prompt(
    *,
    system_prompt: str,
    available_skills: Sequence[SkillMetadata],
    available_tools: Sequence[ToolSpec] | None = None,
    current_datetime: datetime | None = None,
    current_working_directory: Path | None = None,
) -> str:
    skills_section = format_available_skills_section(available_skills)
    with_runtime_fill = _fill_runtime_placeholders(
        system_prompt=system_prompt,
        available_skills_section=skills_section,
        available_tools=available_tools,
        current_datetime=current_datetime,
        current_working_directory=current_working_directory,
    )
    if "<RUNTIME_FILL:SKILLS_SECTION>" in system_prompt:
        return with_runtime_fill
    if not skills_section:
        return with_runtime_fill
    return f"{with_runtime_fill}\n\n{skills_section}"


def _fill_runtime_placeholders(
    *,
    system_prompt: str,
    available_skills_section: str,
    available_tools: Sequence[ToolSpec] | None,
    current_datetime: datetime | None,
    current_working_directory: Path | None,
) -> str:
    active_tools = tuple(available_tools) if available_tools is not None else _default_tool_specs()
    rendered_tools = _format_available_tools(active_tools)
    timestamp = (current_datetime or datetime.now().astimezone()).isoformat(timespec="seconds")
    cwd = str((current_working_directory or Path.cwd()).expanduser().resolve())

    return (
        system_prompt.replace("<RUNTIME_FILL:AVAILABLE_TOOLS>", rendered_tools)
        .replace("<RUNTIME_FILL:SKILLS_SECTION>", available_skills_section)
        .replace("<RUNTIME_FILL:CURRENT_DATETIME>", timestamp)
        .replace("<RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>", cwd)
    )


def _default_tool_specs() -> tuple[ToolSpec, ...]:
    specs: list[ToolSpec] = []
    for tool in builtin_tools():
        specs.append(
            ToolSpec(
                name=str(tool.name),
                description=str(tool.description),
                input_schema=dict(tool.input_schema),
            )
        )
    return tuple(specs)


def _format_available_tools(tools: Sequence[ToolSpec]) -> str:
    if not tools:
        return "(none)"

    lines: list[str] = []
    for tool in tools:
        schema = json.dumps(tool.input_schema, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        lines.append(f"- {tool.name}: {tool.description}")
        lines.append(f"  input_schema: {schema}")
    return "\n".join(lines)
