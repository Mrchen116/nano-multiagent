"""Provider-agnostic request/response contracts for LLM calls."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from nano_multiagent.core.types import TokenUsage, ToolSpec


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    """Represent one tool call emitted by the model."""

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """Represent one message exchanged with the model provider."""

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class LLMGenerateRequest:
    """Describe one model generation request."""

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
    """Describe one normalized model generation response."""

    model: str
    message: LLMMessage
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Protocol implemented by provider-specific generation clients."""

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        """Generate one response for the given normalized request.

        Args:
            request: Provider-agnostic request payload.

        Returns:
            Normalized provider response.
        """

        ...
