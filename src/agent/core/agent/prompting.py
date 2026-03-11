"""Prompt assembly utilities for runtime/system/tool context injection."""
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.core.types import ToolSpec
from agent.core.types import Message
from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.core.skills.formatter import format_available_skills_section
from agent.core.skills.registry import SkillMetadata

LOCAL_CODING_SYSTEM_PROMPT = """You are an expert coding assistant operating inside a coding agent harness. You help users by reading files, executing commands, editing code, and writing new files.

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

CODING_SYSTEM_PROMPT = LOCAL_CODING_SYSTEM_PROMPT

# Generic fallback: empty string signals "product must inject its own prompt".
# Retained as named export to avoid breaking any existing imports; callers that
# relied on the old coding-specific text must migrate to CODING_SYSTEM_PROMPT.
DEFAULT_SYSTEM_PROMPT = ""

_DEFAULT_TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(name="read", description="Read the contents of a file.", input_schema={}),
    ToolSpec(name="write", description="Write content to a file.", input_schema={}),
    ToolSpec(name="edit", description="Edit a file by replacing exact text.", input_schema={}),
    ToolSpec(name="bash", description="Execute a bash command in the current working directory.", input_schema={}),
    ToolSpec(name="task", description="Spawn agent tasks for delegated work.", input_schema={}),
)


def build_prompt_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    available_skills: Sequence[SkillMetadata] = (),
    available_tools: Sequence[ToolSpec] | None = None,
    current_datetime: datetime | str | None = None,
    current_working_directory: Path | None = None,
) -> tuple[LLMMessage, ...]:
    """Build model input messages for one turn.

    Args:
        history_messages: Persisted conversation history before current user input.
        user_text: Current user text input after preprocessing.
        system_prompt: System prompt template.
        available_skills: Skills shown in the rendered system prompt.
        available_tools: Optional explicit tool list; falls back to builtins when omitted.
        current_datetime: Optional timestamp override for deterministic tests.
        current_working_directory: Optional cwd override for deterministic tests.

    Returns:
        Ordered message tuple: system, history, then current user.
    """

    active_system_prompt = build_system_prompt(
        system_prompt=system_prompt,
        available_skills=available_skills,
        available_tools=available_tools,
        current_datetime=current_datetime,
        current_working_directory=current_working_directory,
    )
    messages: list[LLMMessage] = [LLMMessage(role="system", content=active_system_prompt)]
    for message in history_messages:
        metadata = dict(message.metadata)
        messages.append(
            LLMMessage(
                role=message.role,
                content=message.content,
                name=message.name,
                tool_call_id=_extract_tool_call_id(metadata),
                tool_calls=_extract_tool_calls(metadata),
            )
        )
    messages.append(LLMMessage(role="user", content=user_text))
    return tuple(messages)


def build_system_prompt(
    *,
    system_prompt: str,
    available_skills: Sequence[SkillMetadata],
    available_tools: Sequence[ToolSpec] | None = None,
    current_datetime: datetime | str | None = None,
    current_working_directory: Path | None = None,
) -> str:
    """Render system prompt template with runtime placeholders.

    Args:
        system_prompt: Template possibly containing `<RUNTIME_FILL:*` placeholders.
        available_skills: Skills displayed in skills section.
        available_tools: Tool specs rendered into available tools section.
        current_datetime: Optional timestamp override.
        current_working_directory: Optional cwd override.

    Returns:
        Fully rendered system prompt text.
    """

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
    current_datetime: datetime | str | None,
    current_working_directory: Path | None,
) -> str:
    active_tools = tuple(available_tools) if available_tools is not None else _default_tool_specs()
    rendered_tools = _format_available_tools(active_tools)
    timestamp = _resolve_prompt_timestamp(current_datetime)
    cwd = str((current_working_directory or Path.cwd()).expanduser().resolve())

    return (
        system_prompt.replace("<RUNTIME_FILL:AVAILABLE_TOOLS>", rendered_tools)
        .replace("<RUNTIME_FILL:SKILLS_SECTION>", available_skills_section)
        .replace("<RUNTIME_FILL:CURRENT_DATETIME>", timestamp)
        .replace("<RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>", cwd)
    )


def _resolve_prompt_timestamp(current_datetime: datetime | str | None) -> str:
    if isinstance(current_datetime, str):
        stripped = current_datetime.strip()
        if stripped:
            return stripped
    if isinstance(current_datetime, datetime):
        return current_datetime.isoformat(timespec="seconds")
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_tool_specs() -> tuple[ToolSpec, ...]:
    return _DEFAULT_TOOL_SPECS


def _format_available_tools(tools: Sequence[ToolSpec]) -> str:
    if not tools:
        return "(none)"

    return "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)


def _extract_tool_call_id(metadata: Mapping[str, Any]) -> str | None:
    raw_value = metadata.get("tool_call_id")
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    return None


def _extract_tool_calls(metadata: Mapping[str, Any]) -> tuple[LLMToolCall, ...]:
    raw_calls = metadata.get("tool_calls")
    if not isinstance(raw_calls, list):
        return ()
    parsed: list[LLMToolCall] = []
    for item in raw_calls:
        if not isinstance(item, Mapping):
            continue
        call_id = item.get("call_id")
        name = item.get("name")
        arguments = item.get("arguments")
        if not isinstance(call_id, str) or not call_id:
            continue
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(arguments, Mapping):
            arguments = {}
        parsed.append(
            LLMToolCall(
                call_id=call_id,
                name=name,
                arguments=dict(arguments),
            )
        )
    return tuple(parsed)
