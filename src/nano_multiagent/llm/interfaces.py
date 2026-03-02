from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from nano_multiagent.core.types import ToolSpec


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class LLMGenerateRequest:
    session_id: str
    model: str
    messages: tuple[LLMMessage, ...]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[ToolSpec, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMGenerateResponse:
    model: str
    message: LLMMessage
    finish_reason: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        ...
