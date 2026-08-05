"""Represent Gateway run delivery targets and per-run delivery context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from personal_assistant.channels.base import InboundMessage
from personal_assistant.gateway.inbound_models import RelayLifecycleUpdate
from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
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


@dataclass(slots=True)
class RunDeliveryContext:
    """Hold delivery facts and provisional-message state for one kernel run.

    ``visibility_policy`` is fixed when the run is accepted, so every delivery path
    interprets protocol silence tokens consistently. ``discard_empty_completion``
    scopes the stronger direct-Web rule: a successful run must commit visible text or
    its provisional bubble is rolled back. Process events never commit that bubble.
    """

    run_id: str
    agent_id: str
    kernel_session_id: str
    delivery_target: RunDeliveryTarget
    trigger_source: str = ""
    reply_channel_name: str = ""
    reply_target_chat_id: str = ""
    reply_thread_id: str = ""
    feishu_message_id: str = ""
    shadow_saga_id: str = ""
    shadow_message_id: str = ""
    conversation_id: str = ""
    message_id: str = ""
    kernel_message_id: str = ""
    rolling: bool = False
    external_current_text: str = ""
    external_intermediate_sent_marker: str = ""
    visibility_policy: ReplyVisibilityPolicy = ReplyVisibilityPolicy.LITERAL_TEXT
    discard_empty_completion: bool = False
    visible_reply_committed: bool = False
    discard_current_bubble: bool = False

    def ensure_initial_runtime_state(self) -> None:
        """Initialize runtime delivery ids from the static delivery target."""

        if self.conversation_id:
            return
        if self.delivery_target.kind != "shadow":
            return
        shadow_ref = self.delivery_target.shadow_ref
        if shadow_ref is not None:
            self.conversation_id = shadow_ref.conversation_id

    @property
    def owner_user_id(self) -> str:
        """Return the owner-direct user id, if this run has one."""

        owner_direct = self.delivery_target.owner_direct
        return owner_direct.to_user_id if owner_direct is not None else ""

    def begin_roll(self) -> bool:
        """Claim the current bubble-roll transition when no roll is active."""

        if self.rolling:
            return False
        self.rolling = True
        return True

    def finish_roll(self) -> None:
        """Release the current bubble-roll transition."""

        self.rolling = False

    def reset_bubble_state(self) -> None:
        """Clear state that belongs to the bubble just closed or discarded."""

        self.kernel_message_id = ""
        self.external_current_text = ""
        self.external_intermediate_sent_marker = ""
        self.visible_reply_committed = False
        self.discard_current_bubble = False

    def record_shadow_snapshot(self, shadow_message_id: str) -> None:
        """Remember the durable shadow message representing the current bubble."""

        self.shadow_message_id = shadow_message_id

    def switch_shadow_saga(self, shadow_saga_id: str) -> None:
        """Move subsequent delivery to another shadow saga and clear its anchor."""

        self.shadow_saga_id = shadow_saga_id
        self.shadow_message_id = ""

    def resolve_conversation(self, conversation_id: str) -> None:
        """Record the canonical IM conversation selected for this live run."""

        self.conversation_id = conversation_id

    def mark_external_intermediate_sent(self, marker: str) -> None:
        """Remember which external text snapshot has already been mirrored."""

        self.external_intermediate_sent_marker = marker

    def record_assistant_text(
        self, text: str, *, kernel_message_id: str | None = None
    ) -> None:
        """Capture the latest assistant text and, when present, its kernel id."""

        if kernel_message_id:
            self.kernel_message_id = kernel_message_id
        self.external_current_text = text

    def clear_external_text(self) -> None:
        """Forget the current external text after a suppressed reply."""

        self.external_current_text = ""

    def mark_suppressed_reply(self) -> None:
        """Record protocol silence for a provisional bubble, if one exists."""

        if self.message_id and not self.kernel_message_id:
            self.discard_current_bubble = True
        self.clear_external_text()

    def mark_visible_reply(self) -> None:
        """Commit the current bubble after real assistant text crosses delivery."""

        self.preserve_current_bubble()
        self.visible_reply_committed = True

    def preserve_current_bubble(self) -> None:
        """Cancel an earlier provisional-silence decision for this bubble."""

        self.discard_current_bubble = False

    def backfill_turn_start_ack(
        self,
        *,
        message_id: str | None = None,
        conversation_id: str | None = None,
        kernel_message_id: str | None = None,
    ) -> None:
        """Apply the identifiers returned by an acknowledged turn-start request."""

        if message_id:
            self.message_id = message_id
        if conversation_id:
            self.resolve_conversation(conversation_id)
        if kernel_message_id:
            self.kernel_message_id = kernel_message_id

    def clear_message_id(self) -> None:
        """Mark the current bubble unavailable while preserving its delivery target."""

        self.message_id = ""

    def replace_bubble(
        self, *, message_id: str, kernel_message_id: str | None = None
    ) -> None:
        """Point this run at a newly acknowledged delivery bubble."""

        self.message_id = message_id
        self.reset_bubble_state()
        self.kernel_message_id = kernel_message_id or ""


@dataclass(frozen=True, slots=True)
class RunDeliveryTerminalProjection:
    """Expose the only delivery fact scheduler terminal consumers need."""

    resolved_conversation_id: str | None


class RunDeliveryContextStore:
    """Own the single typed delivery context for each live kernel run."""

    def __init__(self) -> None:
        self._contexts: dict[str, RunDeliveryContext] = {}

    def get(self, run_id: str) -> RunDeliveryContext | None:
        """Return typed context for one run, if present."""

        return self._contexts.get(run_id)

    def seed_owner_direct_run(
        self,
        *,
        run_id: str,
        agent_id: str,
        kernel_session_id: str,
        owner_user_id: str,
    ) -> RunDeliveryContext:
        """Seed a heartbeat/cron owner-direct delivery context."""

        delivery_target = (
            RunDeliveryTarget.for_owner_direct(
                OwnerDirectTarget(to_user_id=owner_user_id, agent_id=agent_id)
            )
            if owner_user_id
            else RunDeliveryTarget.none(reason="owner_user_missing")
        )
        return self.seed(
            RunDeliveryContext(
                run_id=run_id,
                agent_id=agent_id,
                kernel_session_id=kernel_session_id,
                delivery_target=delivery_target,
                visibility_policy=ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS,
            )
        )

    def take(self, run_id: str) -> RunDeliveryContext | None:
        """Atomically remove and return one live context for its terminal owner."""

        return self._contexts.pop(run_id, None)

    def discard(self, run_id: str) -> bool:
        """Remove one live context and report whether it was still present."""

        return self.take(run_id) is not None

    def seed(self, context: RunDeliveryContext) -> RunDeliveryContext:
        """Store one context without clobbering an already-live run."""

        existing = self._contexts.get(context.run_id)
        if existing is not None:
            return existing
        context.ensure_initial_runtime_state()
        self._contexts[context.run_id] = context
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
        elif protocol.external_source is not None:
            delivery_target = RunDeliveryTarget.none(reason="external_without_shadow")
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
                shadow_saga_id=protocol.shadow_saga_id or "",
                # Web relay owns the provisional Web IM bubble, so a protocol
                # silence token must tombstone it instead of surviving history.
                # Other shadow transports retain their pre-existing literal policy.
                visibility_policy=(
                    ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
                    if message.is_group
                    or message.channel_name == "web_relay"
                    or delivery_target.kind == "owner_direct"
                    or protocol.external_source is not None
                    else ReplyVisibilityPolicy.LITERAL_TEXT
                ),
                # Only the canonical Web relay owns a provisional browser bubble whose
                # successful process-only terminal state means protocol silence. Other
                # transports keep their existing completion semantics.
                discard_empty_completion=message.channel_name == "web_relay",
            )
        )
