"""Runtime guardrail policies for turn limits, history, and tool calls."""

from dataclasses import dataclass
from typing import TypeVar

from nano_multiagent.core.errors import PolicyViolation

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AgentPolicies:
    """Bound runtime resource usage and fail fast on policy violations."""

    max_turns: int = 32
    max_context_messages: int = 24
    max_tool_calls: int = 16

    def ensure_turn_allowed(self, *, turn_count: int) -> None:
        """Assert turn count is still within configured limit.

        Raises:
            PolicyViolation: If turn limit is exceeded.
        """

        if turn_count >= self.max_turns:
            raise PolicyViolation(
                "max_turns exceeded",
                details={
                    "max_turns": self.max_turns,
                    "turn_count": turn_count,
                },
            )

    def truncate_history(self, messages: tuple[T, ...]) -> tuple[T, ...]:
        """Trim history to the configured context window size."""

        if self.max_context_messages <= 0:
            return ()
        if len(messages) <= self.max_context_messages:
            return messages
        return messages[-self.max_context_messages :]

    def ensure_tool_calls_allowed(self, *, tool_call_count: int) -> None:
        """Assert cumulative tool calls in a turn stay within policy limit.

        Raises:
            PolicyViolation: If tool call limit is exceeded.
        """

        if tool_call_count > self.max_tool_calls:
            raise PolicyViolation(
                "max_tool_calls exceeded",
                details={
                    "max_tool_calls": self.max_tool_calls,
                    "tool_call_count": tool_call_count,
                },
            )
