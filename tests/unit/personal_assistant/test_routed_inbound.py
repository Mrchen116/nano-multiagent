"""Contracts for Gateway-owned post-ingress routing state."""

from __future__ import annotations

import pytest

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.inbound_models import (
    GatewayShadowState,
    RoutedInbound,
    ShadowConversationRef,
)


def _message() -> InboundMessage:
    return InboundMessage(
        channel_name="synthetic",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )


def test_routed_inbound_defaults_to_empty_shadow_state() -> None:
    routed = RoutedInbound(message=_message())

    assert routed.shadow == GatewayShadowState()
    assert routed.shadow.saga_id is None
    assert routed.shadow.ref is None


def test_gateway_shadow_state_accepts_pending_and_anchored_states() -> None:
    ref = ShadowConversationRef(
        conversation_id="conversation-1",
        im_message_id="message-1",
    )

    assert GatewayShadowState(saga_id="saga-1") == GatewayShadowState(
        saga_id="saga-1",
        ref=None,
    )
    assert GatewayShadowState(saga_id="saga-1", ref=ref).ref == ref


def test_gateway_shadow_state_rejects_ref_without_saga() -> None:
    with pytest.raises(ValueError, match="ref requires saga_id"):
        GatewayShadowState(
            ref=ShadowConversationRef(
                conversation_id="conversation-1",
                im_message_id="message-1",
            )
        )


@pytest.mark.parametrize("field_name", ["conversation_id", "im_message_id"])
def test_shadow_ref_rejects_empty_identity(field_name: str) -> None:
    values = {"conversation_id": "conversation-1", "im_message_id": "message-1"}
    values[field_name] = "  "

    with pytest.raises(ValueError, match=field_name):
        ShadowConversationRef(**values)


def test_shadow_ref_has_no_relay_or_saga_identity() -> None:
    ref = ShadowConversationRef(
        conversation_id="conversation-1",
        im_message_id="message-1",
    )

    assert not hasattr(ref, "relay_task_id")
    assert not hasattr(ref, "shadow_saga_id")
