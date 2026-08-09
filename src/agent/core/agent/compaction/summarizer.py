"""Generate compaction summaries from dropped conversation history."""

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Sequence

from agent.core.agent.state import AgentState, InputPart
from agent.core.hooks.context import HookContext
from agent.core.session.context_state import SessionFileState
from agent.core.types import Message

from .prompts import format_compact_summary, get_compact_prompt

if TYPE_CHECKING:
    from agent.core.agent.context_fork import AgentContextFork

_log = logging.getLogger("agent.core.agent.compaction")


class CompactionSummarizer:
    """Summarize dropped history without fabricating a successful result."""

    def __init__(
        self, *, fork: "AgentContextFork", has_dedicated_model: bool = False
    ) -> None:
        self._fork = fork
        # bugfix-443 fix1 (altitude #3): own the summary_model mutual-exclusion
        # here instead of duplicating `None if dedicated else override` at every
        # call site. A dedicated fork has a fixed model and must ignore the run's
        # model_override; a shared fork follows it.
        self._has_dedicated_model = has_dedicated_model

    async def summarize(
        self,
        *,
        session_id: str,
        system_prompt: str | None,
        dropped_messages: Sequence[Message],
        model_override: str | None = None,
        focus: str | None = None,
        hook_ctx: HookContext | None = None,
    ) -> str | None:
        """Summarize dropped messages for compaction record.

        Builds the LLM request by reusing the main agent's context prefix:
        system_prompt + dropped_messages + summary user message.

        Args:
            session_id: Session id used for provider tracing.
            system_prompt: Rendered system prompt (with tools/skills/cwd/datetime)
                           matching the main agent's actual context.
            dropped_messages: Messages that will be removed from active context.

        Returns:
            Generated summary, or ``None`` when no valid summary was produced.
        """

        if not dropped_messages:
            return None

        history = list(dropped_messages)
        summary_prompt = get_compact_prompt(focus=focus)

        state = AgentState(
            session_id=session_id,
            turn_id="compact",
            turn_count=0,
            history_messages=tuple(history),
            input_parts=(InputPart(type="text", text=""),),
            user_text=summary_prompt,
        )
        sidechain_hook_ctx = (
            replace(
                hook_ctx,
                session_event_publisher=lambda _event, _data: None,
                permission_requester=None,
            )
            if hook_ctx is not None
            else None
        )

        try:
            result = await self._fork.execute(
                state=state,
                max_turns=1,
                session_file_state=SessionFileState(),
                system_prompt_override=system_prompt,
                available_skills_override=(),
                available_tools_override=(),
                # bugfix-429 fix-r1 #2: summarize with the run's model, not the
                # build-time default. bugfix-443 fix1: a dedicated summary_model
                # fork keeps its own model — ignore the per-run override for it.
                model_override=(None if self._has_dedicated_model else model_override),
                # Preserve workspace-scoped hooks and model routing, but keep the
                # internal summary stream out of the parent session event channel.
                hook_ctx=sidechain_hook_ctx,
            )
            summary = result.messages[-1].content.strip() if result.messages else ""
            if summary:
                return format_compact_summary(summary) or None
            return None
        except Exception as exc:
            _log.warning("compaction summarizer failed: %s", exc)
            return None
