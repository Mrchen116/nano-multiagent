"""Shared Channel adapter contracts and gateway message envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ExternalInboundEventIdentity:
    """Identify one provider event independently of its conversation routing.

    Args:
        connector_account_id: Stable account/application identity at the provider.
        provider_event_id: Stable provider event or message identity.
    """

    connector_account_id: str
    provider_event_id: str


@dataclass(frozen=True, slots=True)
class ExternalConversationIdentity:
    """Identify an external-channel conversation represented by an inbound."""

    external_source: str
    external_chat_id: str
    agent_id: str | None = None
    conversation_type: str | None = None
    trigger_source: str | None = None


@dataclass(frozen=True, slots=True)
class IMRelayIngress:
    """Carry transport facts normalized from one IM relay payload."""

    relay_task_id: str
    idempotency_key: str
    im_message_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.relay_task_id, str) or not self.relay_task_id.strip():
            raise ValueError("relay_task_id must be a non-empty string")
        if (
            not isinstance(self.idempotency_key, str)
            or not self.idempotency_key.strip()
        ):
            raise ValueError("idempotency_key must be a non-empty string")


@dataclass(frozen=True, slots=True)
class InboundIngress:
    """Carry normalized transport and provider identities into the Gateway."""

    im_relay: IMRelayIngress | None = None
    external_conversation: ExternalConversationIdentity | None = None
    external_event: ExternalInboundEventIdentity | None = None

    def __post_init__(self) -> None:
        if self.external_event is not None and self.external_conversation is None:
            raise ValueError("external_event requires external_conversation")


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
        ingress: Normalized transport and provider identities for Gateway routing.
        source_timestamp: Provider occurrence time normalized to aware UTC.
        received_timestamp: Gateway acceptance time normalized to aware UTC.
    """

    channel_name: str
    text: str
    external_user_id: str
    external_chat_id: str
    is_group: bool
    agent_id: str | None = None
    thread_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    ingress: InboundIngress = field(default_factory=InboundIngress)
    source_timestamp: datetime | None = None
    received_timestamp: datetime | None = None


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


class ChannelStartupError(RuntimeError):
    """Carry one provider-owned startup reason to the lifecycle/status boundary.

    Args:
        status_code: Stable machine-readable provider failure category.
        message: Secret-free user-facing remediation summary.
    """

    def __init__(self, status_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class ChannelAdapter(Protocol):
    """Define the minimal process-local channel adapter contract."""

    name: str

    def start(self, on_inbound: InboundHandler) -> None:
        """Start the adapter and register the gateway inbound callback."""

    def send(self, outbound: OutboundMessage) -> None:
        """Send one outbound message back to the external channel."""

    def stop(self) -> None:
        """Stop the adapter and release any held resources."""
