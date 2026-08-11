"""Contracts for normalized channel ingress facts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from personal_assistant.channels.base import (
    ExternalConversationIdentity,
    ExternalInboundEventIdentity,
    IMRelayIngress,
    InboundIngress,
    InboundMessage,
)


def test_inbound_message_defaults_to_empty_ingress() -> None:
    message = InboundMessage(
        channel_name="synthetic",
        text="wake up",
        external_user_id="system",
        external_chat_id="system",
        is_group=False,
    )

    assert message.ingress == InboundIngress()
    assert message.ingress.im_relay is None
    assert message.ingress.external_conversation is None
    assert message.ingress.external_event is None


def test_external_event_requires_external_conversation() -> None:
    with pytest.raises(
        ValueError,
        match="external_event requires external_conversation",
    ):
        InboundIngress(
            external_event=ExternalInboundEventIdentity(
                connector_account_id="cli-a",
                provider_event_id="msg-1",
            )
        )


@pytest.mark.parametrize("field_name", ["relay_task_id", "idempotency_key"])
def test_im_relay_required_identity_rejects_empty_values(field_name: str) -> None:
    values = {"relay_task_id": "relay-1", "idempotency_key": "idem-1"}
    values[field_name] = "  "

    with pytest.raises(ValueError, match=field_name):
        IMRelayIngress(**values)


def test_ingress_values_are_immutable() -> None:
    ingress = InboundIngress(
        im_relay=IMRelayIngress(
            relay_task_id="relay-1",
            idempotency_key="idem-1",
        ),
        external_conversation=ExternalConversationIdentity(
            external_source="feishu",
            external_chat_id="oc-product",
        ),
    )

    with pytest.raises(FrozenInstanceError):
        ingress.im_relay = None  # type: ignore[misc]
