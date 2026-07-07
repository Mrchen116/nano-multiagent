"""Represent Gateway run delivery targets and per-run delivery context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.inbound_pipeline import RelayLifecycleUpdate
from personal_assistant.gateway.runtime_protocol import (
    ShadowConversationRef,
    runtime_protocol_or_derive,
)


@dataclass(frozen=True, slots=True)
class OwnerDirectTarget:
    """Identify the canonical owner direct chat target for proactive runs."""

    to_user_id: str
    agent_id: str


@dataclass(frozen=True, slots=True)
class RunDeliveryTarget:
    """Describe the IM-visible target for one kernel run.

    The three variants deliberately keep owner proactive delivery separate from
    shadow conversations. Heartbeat and cron create an owner direct chat lazily;
    they must never masquerade as an external-channel shadow conversation.
    """

    kind: Literal["shadow", "owner_direct", "none"]
    shadow_ref: ShadowConversationRef | None = None
    owner_direct: OwnerDirectTarget | None = None
    reason: str | None = None

    @classmethod
    def shadow(cls, shadow_ref: ShadowConversationRef) -> RunDeliveryTarget:
        """Build a shadow conversation delivery target."""

        return cls(kind="shadow", shadow_ref=shadow_ref)

    @classmethod
    def for_owner_direct(cls, owner_direct: OwnerDirectTarget) -> RunDeliveryTarget:
        """Build an owner direct lazy-delivery target."""

        return cls(kind="owner_direct", owner_direct=owner_direct)

    @classmethod
    def none(cls, *, reason: str | None = None) -> RunDeliveryTarget:
        """Build an explicit no-IM-delivery target."""

        return cls(kind="none", reason=reason)


@dataclass(frozen=True, slots=True)
class RunDeliveryContext:
    """Hold delivery facts for one kernel run."""

    run_id: str
    agent_id: str
    kernel_session_id: str
    delivery_target: RunDeliveryTarget
    trigger_source: str = ""
    reply_channel_name: str = ""
    reply_target_chat_id: str = ""
    reply_thread_id: str = ""
    feishu_message_id: str = ""

    def to_legacy_dict(self) -> dict[str, str]:
        """Return the dict shape consumed by the pre-extraction observer."""

        if self.delivery_target.kind == "shadow":
            shadow_ref = self.delivery_target.shadow_ref
            conversation_id = shadow_ref.conversation_id if shadow_ref else ""
            to_user_id = ""
        elif self.delivery_target.kind == "owner_direct":
            owner_direct = self.delivery_target.owner_direct
            conversation_id = ""
            to_user_id = owner_direct.to_user_id if owner_direct else ""
        else:
            conversation_id = ""
            to_user_id = ""

        fields: dict[str, str] = {
            "conversation_id": conversation_id,
            "message_id": "",
            "agent_id": self.agent_id,
            "kernel_session_id": self.kernel_session_id,
            "to_user_id": to_user_id,
        }
        optional = {
            "trigger_source": self.trigger_source,
            "reply_channel_name": self.reply_channel_name,
            "reply_target_chat_id": self.reply_target_chat_id,
            "reply_thread_id": self.reply_thread_id,
            "feishu_message_id": self.feishu_message_id,
        }
        fields.update({key: value for key, value in optional.items() if value})
        return fields


class RunDeliveryContextStore:
    """Own typed run delivery contexts and the legacy observer view."""

    def __init__(self) -> None:
        self._contexts: dict[str, RunDeliveryContext] = {}
        self._legacy_contexts: dict[str, dict[str, str]] = {}

    @property
    def legacy_contexts(self) -> dict[str, dict[str, str]]:
        """Return the mutable legacy context map used during extraction."""

        return self._legacy_contexts

    def get(self, run_id: str) -> RunDeliveryContext | None:
        """Return typed context for one run, if present."""

        return self._contexts.get(run_id)

    def discard(self, run_id: str) -> None:
        """Remove typed and legacy context for one run."""

        self._contexts.pop(run_id, None)
        self._legacy_contexts.pop(run_id, None)

    def seed(self, context: RunDeliveryContext) -> RunDeliveryContext:
        """Store one context without clobbering an already-live run."""

        existing = self._contexts.get(context.run_id)
        if existing is not None:
            return existing
        self._contexts[context.run_id] = context
        self._legacy_contexts[context.run_id] = context.to_legacy_dict()
        return context

    def seed_from_lifecycle(
        self,
        *,
        message: InboundMessage,
        update: RelayLifecycleUpdate,
        owner_user_id: str,
    ) -> RunDeliveryContext | None:
        """Seed context from an accepted relay lifecycle update."""

        if not update.run_id:
            return None
        existing = self._contexts.get(update.run_id)
        if existing is not None:
            return existing

        protocol = runtime_protocol_or_derive(message)
        external_identity = protocol.external_identity
        trigger_source = protocol.trigger_source or ""
        agent_id = (external_identity.agent_id if external_identity else None) or (
            update.agent_id or ""
        )

        if protocol.shadow_ref is not None:
            delivery_target = RunDeliveryTarget.shadow(protocol.shadow_ref)
        elif protocol.relay_task_id is not None:
            delivery_target = RunDeliveryTarget.shadow(
                ShadowConversationRef(
                    conversation_id=message.external_chat_id,
                    relay_task_id=protocol.relay_task_id,
                    im_message_id=protocol.im_message_id,
                )
            )
        elif external_identity is not None:
            delivery_target = RunDeliveryTarget.none(
                reason="external_without_shadow"
            )
        elif owner_user_id:
            delivery_target = RunDeliveryTarget.for_owner_direct(
                OwnerDirectTarget(to_user_id=owner_user_id, agent_id=agent_id)
            )
        else:
            delivery_target = RunDeliveryTarget.none(reason="owner_user_missing")

        reply_channel_name = ""
        reply_target_chat_id = ""
        reply_thread_id = ""
        feishu_message_id = ""
        if trigger_source and trigger_source != "im":
            reply_channel_name = str(getattr(message, "channel_name", "") or "")
            reply_target_chat_id = message.external_chat_id
            thread_id = getattr(message, "thread_id", None)
            reply_thread_id = str(thread_id) if thread_id else ""
            raw_feishu_message_id = message.metadata.get("feishu_message_id")
            feishu_message_id = (
                raw_feishu_message_id.strip()
                if isinstance(raw_feishu_message_id, str)
                and raw_feishu_message_id.strip()
                else ""
            )

        return self.seed(
            RunDeliveryContext(
                run_id=update.run_id,
                agent_id=agent_id,
                kernel_session_id=update.kernel_session_id or "",
                delivery_target=delivery_target,
                trigger_source=trigger_source,
                reply_channel_name=reply_channel_name,
                reply_target_chat_id=reply_target_chat_id,
                reply_thread_id=reply_thread_id,
                feishu_message_id=feishu_message_id,
            )
        )
