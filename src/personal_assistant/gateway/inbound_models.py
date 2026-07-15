"""Shared typed values for the Gateway inbound ownership graph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from personal_assistant.channels.base import InboundMessage, OutboundMessage


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
