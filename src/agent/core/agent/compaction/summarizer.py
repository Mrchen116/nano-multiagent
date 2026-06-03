"""Generate compaction summaries from dropped conversation history."""

import logging
from typing import TYPE_CHECKING, Sequence

from agent.core.agent.state import AgentState, InputPart
from agent.core.tools.session_file_state import SessionFileState
from agent.core.types import Message

from .prompts import format_compact_summary, get_compact_prompt

if TYPE_CHECKING:
    from agent.core.agent.context_fork import AgentContextFork

_log = logging.getLogger("agent.core.agent.compaction")


class CompactionSummarizer:
    """Summarize dropped history via LLM with deterministic fallback."""

    def __init__(self, *, fork: "AgentContextFork") -> None:
        self._fork = fork

    async def summarize(
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

        history = list(dropped_messages)
        summary_prompt = get_compact_prompt()

        state = AgentState(
            session_id=session_id,
            turn_id="compact",
            turn_count=0,
            history_messages=tuple(history),
            input_parts=(InputPart(type="text", text=""),),
            user_text=summary_prompt,
        )

        try:
            result = await self._fork.execute(
                state=state,
                max_turns=1,
                session_file_state=SessionFileState(),
                system_prompt_override=system_prompt,
                available_skills_override=(),
                available_tools_override=(),
            )
            summary = result.messages[-1].content.strip() if result.messages else ""
            return format_compact_summary(summary) if summary else _fallback_summary()
        except Exception as exc:
            _log.exception(
                "compaction summarizer failed; using fallback summary: %s", exc
            )
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
