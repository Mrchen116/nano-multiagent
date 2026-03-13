"""Web IM relay channel adapter fed by IM websocket downstream frames."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from personal_assistant.channels.base import InboundHandler, InboundMessage, OutboundMessage


@dataclass(frozen=True, slots=True)
class RelayEnvelope:
    """Represent one downstream relay.message payload from IM.

    Args:
        relay_task_id: Relay task identifier created by IM service.
        idempotency_key: Upstream idempotency key for this relay delivery.
        sender_user_id: User id that authored the Web IM message.
        conversation_id: IM conversation id used as the external chat id.
        content: Plain-text message content.
        agent_id: Optional explicit target agent.
        metadata: Opaque remaining relay metadata.
    """

    relay_task_id: str
    idempotency_key: str
    sender_user_id: str
    conversation_id: str
    content: str
    agent_id: str | None
    metadata: Mapping[str, Any]


class WebRelayAdapter:
    """Adapt IM relay.message pushes into the gateway channel contract.

    Notes:
        This adapter is process-local and only receives inbound relay frames from the
        IM websocket connection. Outbound sends are normalized and recorded so the
        gateway can inspect what would be delivered back to Web IM.
    """

    name = "web_relay"

    def __init__(self) -> None:
        self._on_inbound: InboundHandler | None = None
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound: InboundHandler) -> None:
        """Store the gateway inbound callback used for relay pushes."""

        self._on_inbound = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        """Record normalized outbound traffic destined for Web IM."""

        self.sent.append(outbound)

    def stop(self) -> None:
        """Detach the current inbound callback."""

        self._on_inbound = None

    def accept_relay(self, payload: Mapping[str, object]) -> InboundMessage:
        """Convert one ``relay.message`` payload into an inbound gateway message.

        Raises:
            RuntimeError: When the adapter has not been started yet.
            ValueError: When required relay fields are missing or malformed.
        """

        callback = self._on_inbound
        if callback is None:
            raise RuntimeError("web relay adapter is not started")
        envelope = _parse_relay_payload(payload)
        conversation_type = envelope.metadata.get("conversation_type")
        inbound = InboundMessage(
            channel_name=self.name,
            text=envelope.content,
            external_user_id=envelope.sender_user_id,
            external_chat_id=envelope.conversation_id,
            is_group=conversation_type == "group",
            agent_id=envelope.agent_id,
            thread_id=_optional_text(envelope.metadata.get("thread_id")),
            metadata={
                "relay_task_id": envelope.relay_task_id,
                "idempotency_key": envelope.idempotency_key,
                **dict(envelope.metadata),
            },
        )
        callback(inbound)
        return inbound


def _parse_relay_payload(payload: Mapping[str, object]) -> RelayEnvelope:
    relay_task_id = _require_text(payload.get("relay_task_id"), field_name="relay_task_id")
    idempotency_key = _require_text(payload.get("idempotency_key"), field_name="idempotency_key")
    message = payload.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("message must be an object")
    sender_user_id = _require_text(message.get("sender_user_id"), field_name="message.sender_user_id")
    conversation_id = _require_text(message.get("conversation_id"), field_name="message.conversation_id")
    content = _require_text(message.get("content"), field_name="message.content")
    metadata = payload.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be an object")
    return RelayEnvelope(
        relay_task_id=relay_task_id,
        idempotency_key=idempotency_key,
        sender_user_id=sender_user_id,
        conversation_id=conversation_id,
        content=content,
        agent_id=_optional_text(payload.get("agent_id")),
        metadata=dict(metadata),
    )


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings when provided")
    stripped = value.strip()
    return stripped or None
