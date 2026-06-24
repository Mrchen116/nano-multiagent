"""Canonical hook event/type declarations shared across runtime and plugins."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Mapping, TypeAlias

DEFAULT_HOOK_PRIORITY = 100
DEFAULT_HOOK_TIMEOUT_MS = 1500


class HookEventType(StrEnum):
    """Enumerate supported hook event names."""

    SESSION_START = "session_start"
    SESSION_COMPACT = "session_compact"
    SESSION_SHUTDOWN = "session_shutdown"
    INPUT = "input"
    BEFORE_AGENT_START = "before_agent_start"
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MESSAGE_START = "message_start"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_END = "message_end"
    TOOL_CALL = "tool_call"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_UPDATE = "tool_execution_update"
    TOOL_EXECUTION_END = "tool_execution_end"
    TOOL_RESULT = "tool_result"
    RUN_ERROR = "run_error"
    RUN_TIMEOUT = "run_timeout"
    RUN_ABORT = "run_abort"
    # bugfix-426-M4 决策6: fired at the round boundary where the loop actually drains
    # and consumes injected (steered) messages into the model context. The gateway
    # turns this into "roll the IM bubble" — only the loop knows this consume point.
    PENDING_INJECTION_CONSUMED = "pending_injection_consumed"


class HookEventMode(StrEnum):
    """Describe whether an event is observe-only, intercept-capable, or background.

    Three orthogonal dispatch modes:
    - observe: blocking, read-only, subject to timeout_ms
    - intercept: blocking, can rewrite/stop payload, subject to timeout_ms
    - background: fire-and-forget via asyncio.create_task, no timeout, can fork conversation
    """

    OBSERVE = "observe"
    INTERCEPT = "intercept"
    # Fire-and-forget mode for long-running side-chains (e.g., self-improvement review).
    # Handlers receive fork_conversation in their HookContext; dispatch does not await.
    BACKGROUND = "background"


INTERCEPT_EVENTS = frozenset(
    {
        HookEventType.INPUT.value,
        HookEventType.BEFORE_AGENT_START.value,
        HookEventType.TOOL_CALL.value,
        HookEventType.TOOL_RESULT.value,
    }
)
OBSERVE_EVENTS = frozenset(
    {event.value for event in HookEventType} - set(INTERCEPT_EVENTS)
)
ALL_HOOK_EVENTS = frozenset({event.value for event in HookEventType})

HookEventName: TypeAlias = str
HookPayload: TypeAlias = Mapping[str, Any]
HookResult: TypeAlias = Mapping[str, Any] | None
HookHandler: TypeAlias = Callable[
    [Mapping[str, Any], "HookContext"], HookResult | Awaitable[HookResult]
]
HookSource: TypeAlias = Literal["builtin", "workspace", "runtime"]

InputHookAction: TypeAlias = Literal["continue", "transform", "handled"]
HookStatus: TypeAlias = Literal["ok", "error", "timeout"]


@dataclass(frozen=True, slots=True)
class HookRegistration:
    """Store normalized metadata for one registered hook handler.

    timeout_ms may be ``None`` to indicate the hook self-manages its time
    boundaries and must not be wrapped in ``asyncio.wait_for``. Use ``None``
    only for security-critical hooks (e.g. auto_mode_gate) that legitimately
    park waiting for user input — the framework's default fail-OPEN timeout
    is incompatible with a security gate that cannot silently succeed.
    """

    event: HookEventName
    handler: HookHandler
    priority: int = DEFAULT_HOOK_PRIORITY
    timeout_ms: int | None = DEFAULT_HOOK_TIMEOUT_MS
    order: int = 0
    source: HookSource = "runtime"
    module_name: str | None = None
    file_path: Path | None = None
    hook_id: str = ""
    # Dispatch mode for this registration. Defaults to OBSERVE.
    # BACKGROUND registrations are handled fire-and-forget without timeout.
    mode: HookEventMode = HookEventMode.OBSERVE


@dataclass(frozen=True, slots=True)
class LoadedHookModule:
    """Describe one imported hook module and its source location."""

    module_name: str
    file_path: Path
    source: HookSource


def normalize_hook_event(event: str | HookEventType) -> str:
    """Normalize enum/string event input to canonical string name."""

    if isinstance(event, HookEventType):
        return event.value
    return str(event)


def ensure_known_hook_event(event: str | HookEventType) -> str:
    """Validate that an event exists in the known hook event set."""

    normalized = normalize_hook_event(event)
    if normalized not in ALL_HOOK_EVENTS:
        raise ValueError(f"unknown hook event: {normalized}")
    return normalized


def event_mode_of(event: str | HookEventType) -> HookEventMode:
    """Return dispatch mode for an event (`intercept` or `observe`)."""

    normalized = ensure_known_hook_event(event)
    if normalized in INTERCEPT_EVENTS:
        return HookEventMode.INTERCEPT
    return HookEventMode.OBSERVE
