from typing import Sequence

from nano_multiagent.core.types import Message
from nano_multiagent.llm.interfaces import LLMMessage
from nano_multiagent.skills.formatter import format_available_skills_section
from nano_multiagent.skills.registry import SkillMetadata

DEFAULT_SYSTEM_PROMPT = (
    "You are nano-multiagent. "
    "Provide concise, useful answers based only on the available conversation context."
)


def build_prompt_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    available_skills: Sequence[SkillMetadata] = (),
) -> tuple[LLMMessage, ...]:
    active_system_prompt = build_system_prompt(
        system_prompt=system_prompt,
        available_skills=available_skills,
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
) -> str:
    skills_section = format_available_skills_section(available_skills)
    if not skills_section:
        return system_prompt
    return f"{system_prompt}\n\n{skills_section}"
