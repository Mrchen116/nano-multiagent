"""Generate compaction summaries from dropped conversation history."""

from typing import Sequence

from agent.core.types import Message
from agent.core.llm.interfaces import LLMClient, LLMGenerateRequest, LLMMessage

from .prompts import COMPACT_MAX_OUTPUT_TOKENS, format_compact_summary, get_compact_prompt


class CompactionSummarizer:
    """Summarize dropped history via LLM with deterministic fallback."""

    def __init__(self, *, llm_client: LLMClient, model: str) -> None:
        self._llm_client = llm_client
        self._model = model

    def summarize(
        self,
        *,
        session_id: str,
        system_prompt: str | None,
        dropped_messages: Sequence[Message],
    ) -> str:
        """Summarize dropped messages for compaction record.

        Builds the LLM request by reusing the main agent's context prefix:
        system_prompt + dropped_messages + summary user message.

        Args:
            session_id: Session id used for provider tracing.
            system_prompt: Rendered system prompt (with tools/skills/cwd/datetime)
                           matching the main agent's actual context.
            dropped_messages: Messages that will be removed from active context.

        Returns:
            Generated summary, or fallback summary on empty input/failure.
        """

        if not dropped_messages:
            return _fallback_summary()

        messages: list[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        for msg in dropped_messages:
            messages.append(LLMMessage(role=msg.role, content=msg.content))
        messages.append(LLMMessage(role="user", content=get_compact_prompt()))

        try:
            response = self._llm_client.generate(
                LLMGenerateRequest(
                    session_id=session_id,
                    model=self._model,
                    messages=tuple(messages),
                    stream=False,
                    max_tokens=COMPACT_MAX_OUTPUT_TOKENS,
                )
            )
            summary = response.message.content.strip()
            return format_compact_summary(summary) if summary else _fallback_summary()
        except Exception:
            return _fallback_summary()


def _fallback_summary() -> str:
    return (
        "Summary:\n"
        "1. Primary Request and Intent: Session continuity maintained.\n"
        "2. Key Technical Concepts: None.\n"
        "3. Files and Code Sections: None.\n"
        "4. Errors and fixes: None.\n"
        "5. Problem Solving: None.\n"
        "6. All user messages: None.\n"
        "7. Pending Tasks: Continue the latest user request.\n"
        "8. Current Work: Context compaction was performed.\n"
        "9. Optional Next Step: Resume directly from the latest user request."
    )
