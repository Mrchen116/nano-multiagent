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
    parent_message_id: str | None = None
    group_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # Preserved for round-trip with thinking-enabled providers (e.g. kimi K2.6).
    # Must be written to JSONL and restored by build_chat_messages so cross-restart
    # sessions don't receive "reasoning_content is missing" rejections.
    reasoning_content: str | None = None
    reasoning_signature: str | None = None
    # bugfix-433 决策4: structured content blocks (e.g. image) that ``content:str``
    # cannot carry. When present this is the authoritative multimodal representation;
    # ``content`` stays a plain-text projection (for search/logging/text fallback).
    # Written to JSONL only when non-empty and restored by build_chat_messages so
    # images survive cross-turn replay; None for pure-text messages (no golden drift).
    parts: tuple[Mapping[str, Any], ...] | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Describe a tool contract exposed to the model."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    is_concurrency_safe: bool = False
    max_result_size_chars: int | None = None


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
    content: str | list[dict[str, Any]] | None = None
    duration_ms: int = 0
    arguments: Mapping[str, Any] = field(default_factory=dict)
    # bugfix-410-M2 (#82/#97): sidecar classification of a non-success terminal
    # state, kept SEPARATE from the model-facing free-text ``error``. Threaded to
    # the IM tool_call badge (denied / timed_out / interrupted). None on success.
    reason_code: str | None = None


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
