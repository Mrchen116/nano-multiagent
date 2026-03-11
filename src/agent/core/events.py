"""Runtime event schema shared by observability and hook pipelines."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .ids import make_event_id


class RuntimeEventType(StrEnum):
    """Enumerate event kinds emitted by the runtime lifecycle."""

    INPUT = "input"
    SESSION_START = "session_start"
    SESSION_COMPACT = "session_compact"
    SESSION_SHUTDOWN = "session_shutdown"
    BEFORE_AGENT_START = "before_agent_start"
    TURN_START = "turn_start"
    MESSAGE_UPDATE = "message_update"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_ERROR = "run_error"
    RUN_TIMEOUT = "run_timeout"
    RUN_ABORT = "run_abort"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """Represent one immutable runtime event record."""

    event_id: str
    type: RuntimeEventType
    session_id: str
    turn_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


def new_runtime_event(
    event_type: RuntimeEventType,
    *,
    session_id: str,
    turn_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> RuntimeEvent:
    """Build a runtime event with a generated event id.

    Args:
        event_type: Event type identifier.
        session_id: Session owning this event.
        turn_id: Optional turn identifier when event is turn-scoped.
        payload: Event-specific data payload.

    Returns:
        A runtime event ready for persistence/streaming.
    """

    return RuntimeEvent(
        event_id=make_event_id(),
        type=event_type,
        session_id=session_id,
        turn_id=turn_id,
        payload=payload or {},
    )
