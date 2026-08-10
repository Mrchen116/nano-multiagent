"""Shared typed values for the Gateway inbound ownership graph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot
from personal_assistant.gateway.runtime_protocol import external_identity_from_message
from personal_assistant.gateway.session_keys import build_external_session_key


@dataclass(frozen=True, slots=True)
class InboundRunRequest:
    """Capture one routed message for coordinator admission.

    Args:
        message: Normalized inbound message after any shadow synchronization.
        agent: One immutable live Agent revision captured at the routing boundary.
        session_key: Gateway-local FIFO and active-run coordination key.
        sender_label: Stable display label used for group-message prefixes.
    """

    message: InboundMessage
    agent: LiveAgentSnapshot
    session_key: str
    sender_label: str
    generation: int = 0


@dataclass(frozen=True, slots=True)
class StopRunRequest:
    """Capture one routed stop command for coordinator admission.

    Args:
        message: Normalized inbound control message.
        agent: One immutable live Agent revision captured at the routing boundary.
        session_key: Gateway-local key whose active run should be interrupted.
    """

    message: InboundMessage
    agent: LiveAgentSnapshot
    session_key: str


@dataclass(frozen=True, slots=True)
class NewSessionRequest:
    """Capture one routed request to replace the current Kernel session.

    ``operation_id`` is the stable ingress identity when the channel supplied one.
    Replayed external events and relay tasks use it to return the first reset outcome
    instead of creating another session.
    """

    message: InboundMessage
    agent: LiveAgentSnapshot
    session_key: str
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompactSessionRequest:
    """Capture one routed explicit compaction request.

    ``generation`` freezes the session context that existed when the command
    entered the FIFO. A later ``/new`` therefore cannot make an older queued
    compaction rewrite the fresh context.
    """

    message: InboundMessage
    agent: LiveAgentSnapshot
    session_key: str
    focus: str | None = None
    operation_id: str | None = None
    generation: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowCommandRequest:
    """Capture one active-Workflow slash command from a human conversation."""

    message: InboundMessage
    agent: LiveAgentSnapshot
    session_key: str
    command_text: str
    sender_label: str
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Expose observable outputs from one inbound pipeline execution.

    Args:
        agent_id: Routed agent chosen at the inbound boundary.
        session_key: Canonical Gateway-local session key.
        kernel_session_id: Kernel session bound to the message.
        run_id: Kernel run id created for the message, or empty for control replies.
        reply_text: Final reply text selected for outbound routing.
        outbound: Normalized outbound payload, or ``None`` when delivery is suppressed.
    """

    agent_id: str
    session_key: str
    kernel_session_id: str
    run_id: str
    reply_text: str
    outbound: OutboundMessage | None


@dataclass(frozen=True, slots=True)
class RelayLifecycleUpdate:
    """Describe one relay-visible execution milestone emitted by the pipeline."""

    phase: Literal["accepted", "running", "completed", "failed"]
    agent_id: str
    session_key: str
    run_id: str | None = None
    reply_text: str | None = None
    error: str | None = None
    detail: Mapping[str, Any] | None = None
    usage: Mapping[str, int] | None = None
    kernel_session_id: str | None = None


RelayLifecycleCallback = Callable[
    [InboundMessage, RelayLifecycleUpdate], Awaitable[None]
]


def build_group_context_key(message: InboundMessage, agent_id: str) -> str:
    """Build the shared ignored-chatter partition key for one Agent.

    Args:
        message: Inbound group message from IM or an external channel.
        agent_id: Routed Agent whose background context owns the message.

    Returns:
        Stable external identity key when present, otherwise the Web IM/channel key.
    """

    external_identity = external_identity_from_message(message)
    if external_identity is not None:
        return build_external_session_key(
            external_source=external_identity.external_source,
            external_chat_id=external_identity.external_chat_id,
            agent_id=agent_id,
        )
    return f"{agent_id}:{message.channel_name}:{message.external_chat_id}"
