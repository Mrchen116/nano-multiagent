from dataclasses import dataclass, field
from typing import Any, Mapping

Role = str
StopReason = str


@dataclass(frozen=True, slots=True)
class Message:
    message_id: str
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    name: str
    output: Any = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TurnResult:
    session_id: str
    turn_id: str
    messages: tuple[Message, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    completed: bool = True
    stop_reason: StopReason = "completed"
