"""Typed runtime-delivery fixtures shared by behavior tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
from personal_assistant.gateway.runtime_delivery.context import (
    OwnerDirectTarget,
    RunDeliveryContext,
    RunDeliveryContextStore,
    RunDeliveryTarget,
)
from personal_assistant.gateway.runtime_protocol import ShadowConversationRef


def delivery_context_store(
    entries: Mapping[str, Mapping[str, Any]] | None = None,
) -> RunDeliveryContextStore:
    """Build a typed store from concise behavior-test delivery facts."""

    store = RunDeliveryContextStore()
    for run_id, values in (entries or {}).items():
        conversation_id = str(values.get("conversation_id", ""))
        owner_user_id = str(values.get("to_user_id", ""))
        agent_id = str(values.get("agent_id", ""))
        if owner_user_id:
            target = RunDeliveryTarget.for_owner_direct(
                OwnerDirectTarget(to_user_id=owner_user_id, agent_id=agent_id)
            )
        elif conversation_id:
            target = RunDeliveryTarget.shadow(
                ShadowConversationRef(conversation_id=conversation_id)
            )
        else:
            target = RunDeliveryTarget.none(reason="test_no_delivery_target")

        policy = values.get("visibility_policy", ReplyVisibilityPolicy.LITERAL_TEXT)
        if isinstance(policy, str):
            policy = ReplyVisibilityPolicy(policy)

        store.seed(
            RunDeliveryContext(
                run_id=run_id,
                agent_id=agent_id,
                kernel_session_id=str(values.get("kernel_session_id", "")),
                delivery_target=target,
                trigger_source=str(values.get("trigger_source", "")),
                reply_channel_name=str(values.get("reply_channel_name", "")),
                reply_target_chat_id=str(values.get("reply_target_chat_id", "")),
                reply_thread_id=str(values.get("reply_thread_id", "")),
                feishu_message_id=str(values.get("feishu_message_id", "")),
                shadow_saga_id=str(values.get("shadow_saga_id", "")),
                shadow_message_id=str(values.get("shadow_message_id", "")),
                conversation_id=conversation_id,
                message_id=str(values.get("message_id", "")),
                kernel_message_id=str(values.get("kernel_message_id", "")),
                rolling=_as_bool(values.get("rolling", False)),
                external_current_text=str(values.get("external_current_text", "")),
                external_intermediate_sent_marker=str(
                    values.get("external_intermediate_sent_marker", "")
                ),
                visibility_policy=policy,
                discard_empty_completion=_as_bool(
                    values.get("discard_empty_completion", False)
                ),
                visible_reply_committed=_as_bool(
                    values.get("visible_reply_committed", False)
                ),
                discard_current_bubble=_as_bool(
                    values.get("discard_current_bubble", False)
                ),
            )
        )
    return store


def _as_bool(value: object) -> bool:
    """Accept the compact boolean values used by older behavior-test fixtures."""

    return value is True or value == "1"
