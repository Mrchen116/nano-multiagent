"""Shared Channel adapter contracts and gateway message envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """Represent one normalized inbound message delivered by a channel adapter.

    Args:
        channel_name: Stable adapter name that produced the message.
        text: Plain-text content forwarded to the gateway pipeline.
        external_user_id: Sender identifier on the external channel.
        external_chat_id: Chat or room identifier on the external channel.
        is_group: Whether the message came from a group-like chat context.
        agent_id: Optional explicit target agent supplied by the channel payload.
        thread_id: Optional thread identifier required for threaded reply routing.
        metadata: Opaque adapter-provided metadata forwarded through the pipeline.
    """

    channel_name: str
    text: str
    external_user_id: str
    external_chat_id: str
    is_group: bool
    agent_id: str | None = None
    thread_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplyContext:
    """Capture the original outbound target that a reply must go back to.

    Args:
        channel_name: Adapter name used for the original inbound message.
        target_chat_id: External chat identifier that should receive the reply.
        thread_id: Optional thread identifier for thread-aware channels.
        metadata: Opaque adapter-specific delivery hints.
    """

    channel_name: str
    target_chat_id: str
    thread_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    """Represent one normalized outbound reply emitted by the gateway.

    Args:
        channel_name: Adapter name that should deliver the reply.
        text: Reply text to send.
        target_chat_id: External chat identifier to deliver to.
        thread_id: Optional thread identifier for threaded delivery.
        metadata: Opaque adapter-specific delivery hints.
    """

    channel_name: str
    text: str
    target_chat_id: str
    thread_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


InboundHandler = Callable[[InboundMessage], None]


class ChannelAdapter(Protocol):
    """Define the minimal process-local channel adapter contract."""

    name: str

    def start(self, on_inbound: InboundHandler) -> None:
        """Start the adapter and register the gateway inbound callback."""

    def send(self, outbound: OutboundMessage) -> None:
        """Send one outbound message back to the external channel."""

    def stop(self) -> None:
        """Stop the adapter and release any held resources."""
