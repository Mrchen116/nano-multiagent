from dataclasses import dataclass
from typing import TypeVar

from nano_multiagent.core.errors import PolicyViolation

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AgentPolicies:
    max_turns: int = 32
    max_context_messages: int = 24

    def ensure_turn_allowed(self, *, turn_count: int) -> None:
        if turn_count >= self.max_turns:
            raise PolicyViolation(
                "max_turns exceeded",
                details={
                    "max_turns": self.max_turns,
                    "turn_count": turn_count,
                },
            )

    def truncate_history(self, messages: tuple[T, ...]) -> tuple[T, ...]:
        if self.max_context_messages <= 0:
            return ()
        if len(messages) <= self.max_context_messages:
            return messages
        return messages[-self.max_context_messages :]
