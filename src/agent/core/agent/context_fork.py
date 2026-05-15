"""Fork agent context for isolated side-chain execution."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent.core.agent.loop import AgentLoop, ToolRegistryLike
from agent.core.agent.policies import AgentPolicies
from agent.core.agent.state import AgentState
from agent.core.llm.interfaces import LLMClient
from agent.core.skills.registry import SkillMetadata
from agent.core.tools.session_file_state import SessionFileState
from agent.core.types import Message, ToolSpec, TurnResult


@dataclass(frozen=True)
class ForkResult:
    """Result returned by a fork_conversation call.

    Contains the TurnResult from the forked side-chain execution and a flag
    indicating whether the fork completed normally.
    """

    turn_result: TurnResult
    completed: bool
    # Tool calls made by the fork (names only, for summarizing to the user).
    tool_names_called: tuple[str, ...] = field(default_factory=tuple)


class ForkDeniedError(RuntimeError):
    """Raised when fork_conversation is invoked but not available (e.g., recursion guard)."""


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

    def bind_tool_registry(self, tool_registry: ToolRegistryLike | None) -> None:
        """Propagate a post-construction tool registry binding into the fork loop.

        Called by AgentRuntime.bind_tool_registry so that the fork side-chain has
        the same registry as the main loop.  Without this, forks constructed before
        the registry is available (as in app.py) would run with tool_registry=None
        and exit with stop_reason='tool_registry_unavailable' after the first LLM
        round returns a tool_use call.
        """
        self._loop.bind_tool_registry(tool_registry)

    async def execute(
        self,
        *,
        state: AgentState,
        max_turns: int | None = None,
        session_file_state: SessionFileState | None = None,
        system_prompt_override: str | None = None,
        available_skills_override: tuple[SkillMetadata, ...] | None = None,
        available_tools_override: tuple[ToolSpec, ...] | None = None,
        tool_execution_allowlist: tuple[str, ...] | None = None,
    ) -> TurnResult:
        """Fork the agent context and execute with isolated side effects.

        Args:
            state: Immutable per-turn state with history and user text.
            max_turns: Max LLM call rounds (default None = no limit).
            session_file_state: Optional isolated file state; defaults to empty.
            system_prompt_override: Optional system prompt override.
            available_skills_override: Optional skills override.
            available_tools_override: Optional tools override.
            tool_execution_allowlist: When set, only these tool names may
                actually execute in the fork; others are denied at the
                execution layer (the tool list sent to the LLM is unchanged).

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
            tool_execution_allowlist=tool_execution_allowlist,
        ):
            messages.append(msg)

        return build_turn_result(state.session_id, state.turn_id, messages)


def make_fork_conversation(
    *,
    context_fork: "AgentContextFork",
    rendered_system_prompt: str,
    active_tools: tuple[ToolSpec, ...],
    messages_snapshot: list[Any],
    session_id: str,
    tool_allowlist: tuple[str, ...],
) -> Callable:
    """Build a fork_conversation callable for injection into background HookContext.

    The returned callable wraps AgentContextFork.execute(), forwarding both the
    parent turn's rendered_system_prompt AND active_tools byte-for-byte to the
    fork. Both are part of the provider prefix-cache key; rebuilding or narrowing
    either one causes a cache miss, which would defeat the whole point of the
    background-fork design (decision 1 + decision 6, design.md).

    Tool narrowing is done at the EXECUTION layer, not by reshaping the tool list
    sent to the LLM: the full active_tools list is sent (cache hit), but the fork's
    StreamingToolExecutor denies any tool call whose name is not in tool_allowlist,
    returning a synthetic error result without ever executing the tool. This is
    the "prompt inherit + execution layer narrow" strategy from decision 6.

    Anti-recursion: the fork is built without fork_conversation in its own hook
    context (the runtime that runs the fork side-chain does not have a hook_runner
    with background hooks, so fork_conversation is never injected inside the fork).

    Args:
        context_fork: The AgentContextFork instance owned by the runtime.
        rendered_system_prompt: Parent turn's rendered system prompt bytes.
        active_tools: Full tool specs from the parent turn — passed byte-for-byte
            to the fork LLM so the prefix cache is hit.
        messages_snapshot: Shallow copy of parent turn messages (conversation context).
        session_id: Parent session id.
        tool_allowlist: Names of tools the fork is allowed to actually execute.
            (The per-call tool_allowlist on the returned callable overrides this
            default if provided.)

    Returns:
        An async callable with signature:
            fork_conversation(review_prompt: str, *, tool_allowlist: tuple[str,...],
                              max_turns: int) -> ForkResult
    """

    async def fork_conversation(
        review_prompt: str,
        *,
        tool_allowlist: tuple[str, ...] = (),
        max_turns: int = 16,
    ) -> ForkResult:
        """Execute a fork side-chain with the parent turn's context.

        Args:
            review_prompt: The user message sent to the fork agent.
            tool_allowlist: Tools allowed to actually execute. Enforced at the
                execution layer — the LLM still sees the full inherited tool list.
            max_turns: Max LLM iterations.

        Returns:
            ForkResult with turn_result and summary info.
        """
        from agent.core.ids import make_turn_id

        # Build state for fork: parent history + review_prompt as user turn.
        # Convert messages_snapshot to Message objects if they are raw dicts.
        history_messages: tuple[Message, ...] = tuple(
            m for m in messages_snapshot if isinstance(m, Message)
        )

        fork_state = AgentState(
            session_id=session_id,
            turn_id=make_turn_id(),
            turn_count=0,
            history_messages=history_messages,
            input_parts=[],
            user_text=review_prompt,
        )

        turn_result = await context_fork.execute(
            state=fork_state,
            max_turns=max_turns,
            session_file_state=SessionFileState(),
            # Pass parent system prompt + tools byte-for-byte — must NOT rebuild
            # or narrow either; both are part of the provider prefix-cache key.
            system_prompt_override=rendered_system_prompt,
            available_skills_override=(),
            available_tools_override=active_tools,
            # Tool narrowing happens here, at the execution layer only.
            tool_execution_allowlist=tool_allowlist,
        )

        tool_names_called = tuple(tc.name for tc in (turn_result.tool_calls or ()))
        return ForkResult(
            turn_result=turn_result,
            completed=turn_result.completed,
            tool_names_called=tool_names_called,
        )

    return fork_conversation
