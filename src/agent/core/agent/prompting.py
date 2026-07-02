"""Prompt assembly utilities for runtime/system/tool context injection."""

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.core.background_tasks.notifications import BACKGROUND_TASK_PROMPT_BLOCK
from agent.core.types import ToolSpec
from agent.core.types import Message
from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.core.skills.formatter import format_available_skills_section
from agent.core.skills.registry import SkillMetadata

# ---------------------------------------------------------------------------
# Self-evolution guidance constants (hermes-reference §6)
# Injected into the stable tier of the system prompt when the corresponding
# tool is present in the session toolset.
# ---------------------------------------------------------------------------

SKILLS_GUIDANCE: str = (
    "Use skill_view to inspect listed skills before following them. "
    "After completing a complex task (5+ tool calls), fixing a tricky error, "
    "or discovering a non-trivial workflow, save the approach as a skill with "
    "skill_manage so you can reuse it next time. "
    "When using a skill and finding it outdated, incomplete, or wrong, "
    "patch it immediately with skill_manage(action='patch') — don't wait to be asked. "
    "Skills that aren't maintained become liabilities."
)

_SKILL_VIEW_GUIDANCE: str = (
    "Use skill_view to inspect listed skills before following them."
)

_SKILL_MANAGE_GUIDANCE: str = (
    "After completing a complex task (5+ tool calls), fixing a tricky error, "
    "or discovering a non-trivial workflow, save the approach as a skill with "
    "skill_manage so you can reuse it next time. "
    "When using a skill and finding it outdated, incomplete, or wrong, "
    "patch it immediately with skill_manage(action='patch') — don't wait to be asked. "
    "Skills that aren't maintained become liabilities."
)

MEMORY_GUIDANCE: str = (
    "You have persistent memory across sessions. "
    "Save durable facts using the memory tool: user preferences, environment details, "
    "tool quirks, and stable conventions. "
    "Memory is injected into every turn, so keep it compact and focused on facts that "
    "will still matter later. "
    "Prioritize what reduces future user steering — the most valuable memory is one "
    "that prevents the user from having to correct or remind you again. "
    "Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO "
    "state to memory. "
    "Write memories as declarative facts, not instructions to yourself."
)

# Empty string signals that prompt assembly uses segment-based rendering (not a monolithic f-string template).
DEFAULT_SYSTEM_PROMPT = ""


def build_chat_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
    user_parts: list[dict[str, Any]] | None = None,
) -> tuple[LLMMessage, ...]:
    """Build chat messages (history + current user) without system prompt.

    Args:
        history_messages: Persisted conversation history before current user input.
        user_text: Current user text input after preprocessing.
        user_parts: bugfix-433 决策2 — structured content blocks for the current
            user turn when it carries an image (``[{type:text},{type:image,...}]``).
            None keeps the current user on the ``content:str`` path so pure-text
            turns stay byte-identical (不变量1).

    Returns:
        Ordered message tuple: history, then current user. No system message.
    """
    # bugfix-433-fix2: an image-bearing user turn that triggered a provider error must
    # not re-send its image block on later turns (else it errors again every turn →
    # poisoned session). Mirrors CC normalizeMessagesForAPI errorToBlockTypes: for each
    # synthetic provider-error message, walk back to the nearest user turn carrying an
    # image and strip ONLY its image block — text is kept. Computed BEFORE filtering out
    # the error markers (they're the signal). Scope is image-only: a pure-text user turn
    # has no image block, so pure-text provider-error replay is unchanged.
    image_strip_ids = _image_turns_to_strip_after_error(history_messages)

    # bugfix-380: filter out provider error messages before sending to LLM.
    # These are synthetic assistant messages (is_provider_error=True) that were
    # persisted for IM/CLI display but must not pollute the LLM's context window
    # (mirrors CC isSyntheticApiErrorMessage / normalizeMessagesForAPI pattern).
    history_messages = tuple(m for m in history_messages if not _is_provider_error(m))

    # Coalesce assistant Message rows that share a group_id before converting.
    # When parallel tool_use blocks stream in as separate LLM chunks, each chunk
    # is persisted as its own JSONL row but all share the same group_id (set by
    # loop.py). Without coalescing, build_chat_messages would emit separate
    # assistant LLMMessages whose tool_use↔tool_result pairing breaks on reload.
    history_messages = _coalesce_assistant_group(history_messages)

    messages: list[LLMMessage] = []
    for message in history_messages:
        metadata = dict(message.metadata)
        messages.append(
            LLMMessage(
                role=message.role,
                # bugfix-433 决策4: a history Message that persisted image parts must
                # be replayed as a block list so the model still sees the image on
                # later turns; pure-text messages (parts=None) keep content:str.
                # fix2: when this turn previously triggered a provider error, its image
                # block is stripped here (text kept) so it is not re-sent.
                content=_history_content(
                    message, strip_image=message.message_id in image_strip_ids
                ),
                name=message.name,
                tool_call_id=message.tool_call_id or _extract_tool_call_id(metadata),
                tool_calls=_extract_tool_calls(metadata),
                reasoning_content=message.reasoning_content,
                reasoning_signature=message.reasoning_signature,
            )
        )
    messages = _merge_adjacent_assistant(messages)
    # bugfix-433 决策2: send the current user turn as a block list when it carries an
    # image; otherwise keep the plain-text content (no drift for text-only turns).
    current_content: str | list[dict[str, Any]] = (
        user_parts if user_parts else user_text
    )
    messages.append(LLMMessage(role="user", content=current_content))
    return tuple(messages)


def _message_has_image_parts(message: Message) -> bool:
    return bool(message.parts) and any(
        isinstance(p, Mapping) and p.get("type") == "image" for p in message.parts
    )


def _image_turns_to_strip_after_error(
    history_messages: tuple[Message, ...],
) -> frozenset[str]:
    """Return message_ids of image-bearing user turns that preceded a provider error.

    bugfix-433-fix2 (CC normalizeMessagesForAPI errorToBlockTypes): for each synthetic
    provider-error message, walk backward to the nearest user turn carrying an image and
    mark it — its image block must be stripped on replay so the poison image is not
    re-sent every subsequent turn. Walk stops at the first non-error message that is not
    an image user turn (mirrors CC stopping at the preceding assistant / plain user turn).
    """
    strip: set[str] = set()
    for i, msg in enumerate(history_messages):
        if not _is_provider_error(msg):
            continue
        for j in range(i - 1, -1, -1):
            candidate = history_messages[j]
            if candidate.role == "user" and _message_has_image_parts(candidate):
                strip.add(candidate.message_id)
                break
            if _is_provider_error(candidate):
                continue  # skip stacked error markers
            break  # hit an assistant / non-image user turn → stop
    return frozenset(strip)


def _history_content(
    message: Message, *, strip_image: bool = False
) -> str | list[dict[str, Any]]:
    """Return a history message's LLM content, restoring image blocks from parts.

    When ``strip_image`` is set (fix2: this turn triggered a provider error), image
    blocks are dropped and only text is kept, so the poison image is not re-sent. If no
    text block survives, fall back to the message's str content projection.
    """
    if not _message_has_image_parts(message):
        return message.content
    if not strip_image:
        return [dict(p) for p in message.parts]
    text_blocks = [
        dict(p)
        for p in message.parts
        if isinstance(p, Mapping) and p.get("type") == "text"
    ]
    if text_blocks:
        return text_blocks
    # No text survived the strip → fall back to the plain-text projection.
    return message.content


def build_prompt_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
    user_parts: list[dict[str, Any]] | None = None,
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
        user_parts: bugfix-433-fix1 #5 — structured content blocks for the current user
            turn when it carries an image; forwarded to build_chat_messages so this public
            API does not silently drop images (None keeps the content:str path).
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
    chat_messages = list(
        build_chat_messages(
            history_messages=history_messages,
            user_text=user_text,
            user_parts=user_parts,
        )
    )
    return tuple(
        [LLMMessage(role="system", content=active_system_prompt), *chat_messages]
    )


def build_system_prompt(
    *,
    system_prompt: str,
    available_skills: Sequence[SkillMetadata],
    available_tools: Sequence[ToolSpec] | None = None,
    current_datetime: datetime | str | None = None,
    current_working_directory: Path | None = None,
    memory_block: str | None = None,
) -> str:
    """Render system prompt template with runtime placeholders.

    When ``available_tools`` includes ``skill_manage``, ``SKILLS_GUIDANCE`` is
    appended.  When ``memory`` is included, ``MEMORY_GUIDANCE`` is appended.
    When ``memory_block`` is provided, the rendered MemoryStore block is
    prepended before the background-task instructions.

    Args:
        system_prompt: Template possibly containing ``<RUNTIME_FILL:*``
            placeholders.
        available_skills: Skills displayed in skills section.
        available_tools: Tool specs rendered into available tools section and
            used to determine which guidance constants to inject.
        current_datetime: Optional timestamp override.
        current_working_directory: Optional cwd override.
        memory_block: Pre-rendered MemoryStore block (volatile tier).  Injected
            as-is when supplied; omitted when ``None``.

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
        result = with_runtime_fill
    elif not skills_section:
        result = with_runtime_fill
    else:
        result = f"{with_runtime_fill}\n\n{skills_section}"

    # Inject self-evolution guidance constants for the stable tier.
    # Only when the matching tool is in the session's active toolset.
    tool_names: frozenset[str] = frozenset(t.name for t in (available_tools or ()))
    guidance_parts: list[str] = []
    if "memory" in tool_names:
        guidance_parts.append(MEMORY_GUIDANCE)
    skill_guidance = _render_skill_guidance(tool_names)
    if skill_guidance:
        guidance_parts.append(skill_guidance)
    if guidance_parts:
        result = f"{result}\n\n{' '.join(guidance_parts)}"

    # Inject volatile memory block (MemoryStore snapshot) when provided.
    if memory_block:
        result = f"{result}\n\n{memory_block}"

    # Append background task handling instructions so the model knows how to
    # treat <task-notification> messages delivered from completed workers.
    return f"{result}\n\n{BACKGROUND_TASK_PROMPT_BLOCK}"


def _render_skill_guidance(tool_names: frozenset[str]) -> str:
    parts: list[str] = []
    if "skill_view" in tool_names:
        parts.append(_SKILL_VIEW_GUIDANCE)
    if "skill_manage" in tool_names:
        parts.append(_SKILL_MANAGE_GUIDANCE)
    return " ".join(parts)


def _fill_runtime_placeholders(
    *,
    system_prompt: str,
    available_skills_section: str,
    available_tools: Sequence[ToolSpec] | None,
    current_datetime: datetime | str | None,
    current_working_directory: Path | None,
) -> str:
    active_tools = (
        tuple(available_tools) if available_tools is not None else _default_tool_specs()
    )
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
    # Legacy f-string template path retired; segment assembly owns tool listing now.
    return ()


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


def estimate_llm_context_tokens(
    messages: Sequence[LLMMessage],
    system_prompt: str | None = None,
) -> int:
    """Estimate token count for LLM messages (loop-internal version).

    Args:
        messages: LLM messages (history + user, no system).
        system_prompt: Optional system prompt text to include in estimate.

    Returns:
        Estimated token count.
    """
    total = 0
    if system_prompt:
        total += _estimate_text_tokens(system_prompt)
    for msg in messages:
        content = msg.content
        if isinstance(content, str):
            total += _estimate_text_tokens(content)
        elif isinstance(content, list):
            # content is list[dict] for multimodal; estimate each text part
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    total += _estimate_text_tokens(part["text"])
                else:
                    total += 4  # rough estimate for non-text parts
        else:
            total += _estimate_text_tokens(str(content))
        # Assistant tool_calls carry the function name + JSON arguments. These are
        # part of the real context footprint but were previously unaccounted for —
        # a large omission for tool-heavy turns (read/bash loops), where it caused
        # the threshold check to undershoot the model's true token count
        # (bugfix-412 #103). This path is the fallback when no real usage is known.
        for call in msg.tool_calls or ():
            total += _estimate_text_tokens(call.name)
            total += _estimate_text_tokens(
                json.dumps(call.arguments, ensure_ascii=False, default=str)
            )
    total += 4 + len(messages) * 2
    return total


def _estimate_text_tokens(text: str) -> int:
    normalized = " ".join(text.split())
    if not normalized:
        return 1
    return max(1, (len(normalized) + 7) // 8)


def _coalesce_assistant_group(messages: tuple[Message, ...]) -> tuple[Message, ...]:
    """Merge assistant Message rows that share a group_id into one row.

    Parallel tool_use blocks from a single LLM response stream as separate
    Message rows but all carry the same group_id (set in loop.py). Without
    coalescing, build_chat_messages emits separate assistant LLMMessages whose
    tool_use↔tool_result pairing breaks when history is reloaded from JSONL.
    """
    if not messages:
        return messages

    result: list[Message] = []
    # Map group_id → index in result for fast lookup of the canonical row.
    assistant_group_index: dict[str, int] = {}

    for msg in messages:
        if msg.role == "assistant" and msg.group_id:
            existing_idx = assistant_group_index.get(msg.group_id)
            if existing_idx is not None:
                prev = result[existing_idx]
                # Merge tool_calls from both rows.
                prev_calls = list(prev.metadata.get("tool_calls", []))
                new_calls = list(msg.metadata.get("tool_calls", []))
                merged_meta = {
                    **dict(prev.metadata),
                    "tool_calls": prev_calls + new_calls,
                }
                # replace() preserves prev's identity/structure fields and only
                # overrides the merged ones; any field added to Message later is
                # carried automatically instead of being silently dropped here.
                result[existing_idx] = replace(
                    prev,
                    content=(prev.content or "") + (msg.content or ""),
                    metadata=merged_meta,
                    reasoning_content=prev.reasoning_content or msg.reasoning_content,
                    reasoning_signature=prev.reasoning_signature
                    or msg.reasoning_signature,
                )
            else:
                assistant_group_index[msg.group_id] = len(result)
                result.append(msg)
        else:
            result.append(msg)

    return tuple(result)


def _merge_adjacent_assistant(messages: list[LLMMessage]) -> list[LLMMessage]:
    """Merge adjacent assistant role messages into one (multi-content-blocks)."""
    result: list[LLMMessage] = []
    for msg in messages:
        if msg.role == "assistant" and result and result[-1].role == "assistant":
            prev = result[-1]
            merged_content = (prev.content or "") + (msg.content or "")
            merged_tool_calls = tuple(prev.tool_calls) + tuple(msg.tool_calls)
            result[-1] = LLMMessage(
                role="assistant",
                content=merged_content,
                tool_calls=merged_tool_calls,
                tool_call_id=prev.tool_call_id,
                # Preserve thinking block from the first message so providers that
                # require reasoning round-trip (e.g. kimi K2.6) don't reject the turn.
                reasoning_content=prev.reasoning_content or msg.reasoning_content,
                reasoning_signature=prev.reasoning_signature or msg.reasoning_signature,
            )
        else:
            result.append(msg)
    return result


def _is_provider_error(msg: Message) -> bool:
    """Return True if the message was synthesized by the runtime to surface a provider error.

    Such messages are persisted for IM/CLI display (bugfix-380) but must be stripped
    from the LLM history to avoid polluting the model's context window.
    """
    return bool(msg.metadata.get("is_provider_error"))
