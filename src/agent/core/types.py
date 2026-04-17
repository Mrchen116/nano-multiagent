"""Core value objects shared across runtime, providers, and tools."""

from dataclasses import dataclass, field
from typing import Any, Mapping

Role = str
StopReason = str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Canonical token usage fields shared across runtime boundaries."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class Message:
    """Represent a persisted conversation message."""

    message_id: str
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Describe a tool contract exposed to the model."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    is_concurrency_safe: bool = False


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Capture one tool invocation requested by the assistant."""

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Capture one tool execution outcome returned to the model."""

    call_id: str
    name: str
    output: Any = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TurnResult:
    """Bundle all artifacts produced while handling one user turn."""

    session_id: str
    turn_id: str
    messages: tuple[Message, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    completed: bool = True
    stop_reason: StopReason = "completed"
    usage: TokenUsage | None = None
