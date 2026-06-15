"""Runtime guardrail policies for turn limits, history, and tool calls."""

from dataclasses import dataclass
from typing import TypeVar

from agent.core.errors import PolicyViolation

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AgentPolicies:
    """Bound runtime resource usage and fail fast on policy violations."""

    max_turns: int = 10_000
    max_context_messages: int = 0
    # 0 = 不限（与 max_context_messages 的 0=不限 语义对齐）。工具调用上限是
    # 消费者按场景注入的约束（CLI vs 个人助手 vs 无人值守），core 不替所有人兜
    # 底一个魔数——防失控靠用户中断 + max_turns + 产品侧显式上限（bugfix-412 #102）。
    max_tool_calls: int = 0

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
        """Trim history to the configured context window size.

        When max_context_messages <= 0, no truncation is applied and the full
        message tuple is returned (unlimited context).
        """

        if self.max_context_messages <= 0:
            return messages
        if len(messages) <= self.max_context_messages:
            return messages
        return messages[-self.max_context_messages :]

    def ensure_tool_calls_allowed(self, *, tool_call_count: int) -> None:
        """Assert cumulative tool calls in a turn stay within policy limit.

        When max_tool_calls <= 0, no limit is enforced (unlimited tool calls).

        Raises:
            PolicyViolation: If a positive limit is configured and exceeded.
        """

        if self.max_tool_calls <= 0:
            return
        if tool_call_count > self.max_tool_calls:
            raise PolicyViolation(
                "max_tool_calls exceeded",
                details={
                    "max_tool_calls": self.max_tool_calls,
                    "tool_call_count": tool_call_count,
                },
            )
