"""Provider-agnostic request/response contracts for LLM calls."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from agent.core.types import TokenUsage, ToolSpec


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
    content: str | list[dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    # Preserved for round-trip: providers with thinking enabled (e.g. kimi K2.6) require
    # every assistant+tool_calls message to carry back its original reasoning_content,
    # otherwise the follow-up request is rejected with "reasoning_content is missing".
    reasoning_content: str | None = None


@dataclass(frozen=True, slots=True)
class LLMGenerateRequest:
    """Describe one model generation request."""

    session_id: str
    model: str
    messages: tuple[LLMMessage, ...]
    temperature: float | None = None
    max_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    tools: tuple[ToolSpec, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extra_body: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LLMGenerateResponse:
    """Describe one normalized model generation response (legacy sync wrapper).

    Deprecated: streaming clients yield AsyncIterator[LLMMessage] directly.
    Retained for provider mappers and transitional callers.
    """

    model: str
    message: LLMMessage
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Protocol implemented by provider-specific generation clients."""

    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        """Generate one streaming response for the given normalized request.

        Yields one LLMMessage per completed content block.
        The final yielded message is a terminal metadata message carrying
        finish_reason and usage (content="").

        Args:
            request: Provider-agnostic request payload.
        """

        ...
