"""Gateway-local runtime protocol facts consumed after inbound normalization."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from personal_assistant.channels.base import InboundMessage

_RUNTIME_PROTOCOL_KEY = "__runtime_protocol_facts__"


@dataclass(frozen=True, slots=True)
class ExternalConversationIdentity:
    """Typed identity for an external-channel conversation mirrored through IM."""

    external_source: str
    external_chat_id: str
    agent_id: str | None = None
    conversation_type: str | None = None
    trigger_source: str | None = None


@dataclass(frozen=True, slots=True)
class ShadowConversationRef:
    """IM-visible conversation/message target for relay or shadow delivery."""

    conversation_id: str
    relay_task_id: str | None = None
    im_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeProtocolFacts:
    """Typed Gateway facts derived at the IM relay boundary."""

    relay_task_id: str | None = None
    idempotency_key: str | None = None
    im_message_id: str | None = None
    external_identity: ExternalConversationIdentity | None = None
    shadow_ref: ShadowConversationRef | None = None

    @property
    def trigger_source(self) -> str | None:
        if self.external_identity is None:
            return None
        return self.external_identity.trigger_source


def attach_runtime_protocol(
    message: InboundMessage, facts: RuntimeProtocolFacts
) -> InboundMessage:
    """Return ``message`` with typed protocol facts attached to metadata."""

    metadata = dict(message.metadata)
    metadata[_RUNTIME_PROTOCOL_KEY] = facts
    return replace(message, metadata=metadata)


def runtime_protocol_from_message(
    message: InboundMessage,
) -> RuntimeProtocolFacts | None:
    """Return typed runtime protocol facts attached to an inbound message."""

    value = dict(message.metadata).get(_RUNTIME_PROTOCOL_KEY)
    return value if isinstance(value, RuntimeProtocolFacts) else None


def runtime_protocol_or_derive(message: InboundMessage) -> RuntimeProtocolFacts:
    """Return typed facts, deriving legacy-channel facts when no wrapper exists."""

    attached = runtime_protocol_from_message(message)
    if attached is not None:
        return attached
    return derive_runtime_protocol(message)


def derive_runtime_protocol(message: InboundMessage) -> RuntimeProtocolFacts:
    """Derive runtime facts from legacy metadata for non-WebRelay callers."""

    metadata = dict(message.metadata)
    relay_task_id = _metadata_text(metadata, "relay_task_id")
    im_message_id = _metadata_text(metadata, "message_id")
    external_identity = external_identity_from_metadata(metadata)

    shadow_conversation_id = _metadata_text(metadata, "shadow_conversation_id")
    if shadow_conversation_id is None and relay_task_id is not None:
        shadow_conversation_id = message.external_chat_id.strip() or None
    shadow_ref = (
        ShadowConversationRef(
            conversation_id=shadow_conversation_id,
            relay_task_id=relay_task_id,
            im_message_id=im_message_id,
        )
        if shadow_conversation_id is not None
        else None
    )
    return RuntimeProtocolFacts(
        relay_task_id=relay_task_id,
        idempotency_key=_metadata_text(metadata, "idempotency_key"),
        im_message_id=im_message_id,
        external_identity=external_identity,
        shadow_ref=shadow_ref,
    )


def external_identity_from_message(
    message: InboundMessage,
) -> ExternalConversationIdentity | None:
    """Return external identity from typed protocol facts or legacy metadata."""

    facts = runtime_protocol_from_message(message)
    if facts is not None:
        return facts.external_identity
    return external_identity_from_metadata(dict(message.metadata))


def external_identity_from_metadata(
    metadata: Mapping[str, Any],
) -> ExternalConversationIdentity | None:
    """Parse external conversation identity from metadata if all keys exist."""

    external_source = _metadata_text(metadata, "external_source")
    external_chat_id = _metadata_text(metadata, "external_chat_id")
    if external_source is None or external_chat_id is None:
        return None
    return ExternalConversationIdentity(
        external_source=external_source,
        external_chat_id=external_chat_id,
        agent_id=_metadata_text(metadata, "agent_id"),
        conversation_type=_metadata_text(metadata, "conversation_type"),
        trigger_source=_metadata_text(metadata, "trigger_source"),
    )


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
