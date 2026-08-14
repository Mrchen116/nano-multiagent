"""Represent Gateway run delivery targets and per-run delivery context."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from personal_assistant.gateway.inbound_models import (
    RelayLifecycleUpdate,
    RoutedInbound,
    ShadowConversationRef,
)
from personal_assistant.gateway.reply_visibility import ReplyVisibilityPolicy
from personal_assistant.gateway.runtime_footer import TerminalFooterFacts


@dataclass(frozen=True, slots=True)
class OwnerDirectTarget:
    """Identify the canonical owner direct chat target for proactive runs."""

    to_user_id: str
    agent_id: str


@dataclass(frozen=True, slots=True)
class IMRelayTarget:
    """Identify the native Web IM relay target for one run."""

    conversation_id: str
    relay_task_id: str
    im_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalShadowTarget:
    """Identify one confirmed external-channel shadow target."""

    ref: ShadowConversationRef


@dataclass(frozen=True, slots=True)
class RunDeliveryTarget:
    """Describe the IM-visible target for one kernel run.

    The three variants deliberately keep owner proactive delivery separate from
    shadow conversations. Heartbeat and cron create an owner direct chat lazily;
    they must never masquerade as an external-channel shadow conversation.
    """

    kind: Literal["im_relay", "external_shadow", "owner_direct", "none"]
    im_relay: IMRelayTarget | None = None
    external_shadow: ExternalShadowTarget | None = None
    owner_direct: OwnerDirectTarget | None = None
    reason: str | None = None

    @classmethod
    def for_im_relay(cls, target: IMRelayTarget) -> RunDeliveryTarget:
        """Build a native Web IM relay target."""

        return cls(kind="im_relay", im_relay=target)

    @classmethod
    def for_external_shadow(cls, target: ExternalShadowTarget) -> RunDeliveryTarget:
        """Build an external-channel shadow target."""

        return cls(kind="external_shadow", external_shadow=target)

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
    model: str = ""
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
    external_final_text: str = ""
    terminal_footer_facts: TerminalFooterFacts | None = None
    visibility_policy: ReplyVisibilityPolicy = ReplyVisibilityPolicy.LITERAL_TEXT
    discard_empty_completion: bool = False
    visible_reply_committed: bool = False
    discard_current_bubble: bool = False
    suppressed: bool = False
    visibility_state: Literal["active", "quiescing", "revoked"] = "active"
    visibility_changed: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        """Start every newly accepted run with a visible delivery lease."""

        self.visibility_changed.set()

    def ensure_initial_runtime_state(self) -> None:
        """Initialize runtime delivery ids from the static delivery target."""

        if self.conversation_id:
            return
        if self.delivery_target.im_relay is not None:
            self.conversation_id = self.delivery_target.im_relay.conversation_id
        elif self.delivery_target.external_shadow is not None:
            self.conversation_id = (
                self.delivery_target.external_shadow.ref.conversation_id
            )

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

    def suppress(self, run_id: str) -> None:
        """Fence a reset-superseded run before it creates further visible output."""

        context = self._contexts.get(run_id)
        if context is not None:
            context.suppressed = True
            context.visibility_state = "revoked"
            context.visibility_changed.set()

    def quiesce(self, run_id: str) -> None:
        """Temporarily hold new output while a reset publication is decided."""

        context = self._contexts.get(run_id)
        if context is not None and context.visibility_state == "active":
            context.visibility_state = "quiescing"
            context.visibility_changed.clear()

    def restore(self, run_id: str) -> None:
        """Release deferred output after a reset publication fails."""

        context = self._contexts.get(run_id)
        if context is not None and context.visibility_state == "quiescing":
            context.visibility_state = "active"
            context.visibility_changed.set()

    async def await_visibility(self, run_id: str) -> bool:
        """Wait for a quiesced delivery to become visible or permanently revoked."""

        while True:
            context = self._contexts.get(run_id)
            if context is None or context.visibility_state == "revoked":
                return False
            if context.visibility_state == "active":
                return True
            await context.visibility_changed.wait()

    def is_suppressed(self, run_id: str) -> bool:
        """Return whether a run lost visibility because its chat was reset."""

        context = self._contexts.get(run_id)
        return context is not None and context.visibility_state == "revoked"

    def is_quiescing(self, run_id: str) -> bool:
        """Return whether a reset is holding new output for one run."""

        context = self._contexts.get(run_id)
        return context is not None and context.visibility_state == "quiescing"

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
        routed: RoutedInbound,
        update: RelayLifecycleUpdate,
        owner_user_id: str,
    ) -> RunDeliveryContext | None:
        """Seed context from an accepted relay lifecycle update."""

        if not update.run_id:
            return None
        existing = self._contexts.get(update.run_id)
        if existing is not None:
            return existing

        message = routed.message
        external_identity = message.ingress.external_conversation
        trigger_source = (
            external_identity.trigger_source if external_identity is not None else ""
        ) or ""
        agent_id = (external_identity.agent_id if external_identity else None) or (
            update.agent_id or ""
        )

        if routed.shadow.ref is not None:
            delivery_target = RunDeliveryTarget.for_external_shadow(
                ExternalShadowTarget(ref=routed.shadow.ref)
            )
        elif message.ingress.im_relay is not None:
            relay = message.ingress.im_relay
            delivery_target = RunDeliveryTarget.for_im_relay(
                IMRelayTarget(
                    conversation_id=message.external_chat_id,
                    relay_task_id=relay.relay_task_id,
                    im_message_id=relay.im_message_id,
                )
            )
        elif external_identity is not None:
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
                model=update.model or "",
                trigger_source=trigger_source,
                reply_channel_name=reply_channel_name,
                reply_target_chat_id=reply_target_chat_id,
                reply_thread_id=reply_thread_id,
                feishu_message_id=feishu_message_id,
                shadow_saga_id=routed.shadow.saga_id or "",
                # Web relay owns the provisional Web IM bubble, so a protocol
                # silence token must tombstone it instead of surviving history.
                # Other shadow transports retain their pre-existing literal policy.
                visibility_policy=(
                    ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
                    if message.is_group
                    or message.ingress.im_relay is not None
                    or delivery_target.kind == "owner_direct"
                    or external_identity is not None
                    else ReplyVisibilityPolicy.LITERAL_TEXT
                ),
                # Only the canonical Web relay owns a provisional browser bubble whose
                # successful process-only terminal state means protocol silence. Other
                # transports keep their existing completion semantics.
                discard_empty_completion=message.ingress.im_relay is not None,
            )
        )
