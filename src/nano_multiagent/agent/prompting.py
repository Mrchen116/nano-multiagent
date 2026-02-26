from nano_multiagent.core.types import Message
from nano_multiagent.llm.interfaces import LLMMessage

DEFAULT_SYSTEM_PROMPT = (
    "You are nano-multiagent. "
    "Provide concise, useful answers based only on the available conversation context."
)


def build_prompt_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> tuple[LLMMessage, ...]:
    messages: list[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
    for message in history_messages:
        messages.append(LLMMessage(role=message.role, content=message.content, name=message.name))
    messages.append(LLMMessage(role="user", content=user_text))
    return tuple(messages)
