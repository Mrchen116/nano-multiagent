"""Shared typed values for the Gateway inbound ownership graph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot


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
