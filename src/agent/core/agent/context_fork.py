"""Fork agent context for isolated side-chain execution."""

from pathlib import Path

from agent.core.agent.loop import AgentLoop, ToolRegistryLike
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.state import AgentState
from agent.core.llm.interfaces import LLMClient
from agent.core.skills.registry import SkillMetadata
from agent.core.tools.session_file_state import SessionFileState
from agent.core.types import ToolSpec, TurnResult


class AgentContextFork:
    """Execute a side-chain LLM call reusing the parent agent's context prefix.

    Reuses AgentLoop.run() with isolated side effects.
    Used for: compaction, memory extraction, speculative reasoning, etc.
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        policies: AgentPolicies | None = None,
        system_prompt: str | None = None,
        available_skills: tuple[SkillMetadata, ...] = (),
        available_tools: tuple[ToolSpec, ...] | None = None,
        tool_registry: ToolRegistryLike | None = None,
        current_working_directory: Path | None = None,
    ) -> None:
        self._loop = AgentLoop(
            llm_client=llm_client,
            model=model,
            policies=policies,
            system_prompt=system_prompt,
            available_skills=available_skills,
            available_tools=available_tools,
            tool_registry=tool_registry,
            current_working_directory=current_working_directory,
        )

    async def execute(
        self,
        *,
        state: AgentState,
        max_turns: int | None = None,
        session_file_state: SessionFileState | None = None,
        system_prompt_override: str | None = None,
        available_skills_override: tuple[SkillMetadata, ...] | None = None,
        available_tools_override: tuple[ToolSpec, ...] | None = None,
    ) -> TurnResult:
        """Fork the agent context and execute with isolated side effects.

        Args:
            state: Immutable per-turn state with history and user text.
            max_turns: Max LLM call rounds (default None = no limit).
            session_file_state: Optional isolated file state; defaults to empty.
            system_prompt_override: Optional system prompt override.
            available_skills_override: Optional skills override.
            available_tools_override: Optional tools override.

        Returns:
            Turn result from the forked execution.
        """
        from .runtime import build_turn_result

        messages: list = []
        async for msg in self._loop.run(
            state,
            max_turns=max_turns,
            session_file_state=session_file_state or SessionFileState(),
            system_prompt_override=system_prompt_override,
            available_skills_override=available_skills_override,
            available_tools_override=available_tools_override,
        ):
            messages.append(msg)

        return build_turn_result(state.session_id, state.turn_id, messages)
