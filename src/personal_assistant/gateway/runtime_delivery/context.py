"""Represent Gateway run delivery targets and per-run delivery context."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
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

    def to_legacy_dict(self) -> dict[str, str]:
        """Return the dict shape consumed by the pre-extraction observer."""

        if self.delivery_target.kind == "owner_direct":
            owner_direct = self.delivery_target.owner_direct
            to_user_id = owner_direct.to_user_id if owner_direct else ""
        else:
            to_user_id = ""

        fields: dict[str, str] = {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
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
            "shadow_saga_id": self.shadow_saga_id,
            "kernel_message_id": self.kernel_message_id,
            "external_current_text": self.external_current_text,
            "external_intermediate_sent_marker": self.external_intermediate_sent_marker,
        }
        fields.update({key: value for key, value in optional.items() if value})
        if self.rolling:
            fields["rolling"] = "1"
        if self.discard_current_bubble:
            fields["discard_current_bubble"] = "1"
        if self.discard_empty_completion:
            fields["discard_empty_completion"] = "1"
        if self.visible_reply_committed:
            fields["visible_reply_committed"] = "1"
        return fields


class RunDeliveryRuntimeView(MutableMapping[str, str]):
    """Dict-shaped runtime view that writes through to typed context state."""

    _static_keys = (
        "conversation_id",
        "message_id",
        "agent_id",
        "kernel_session_id",
        "to_user_id",
        "trigger_source",
        "reply_channel_name",
        "reply_target_chat_id",
        "reply_thread_id",
        "feishu_message_id",
        "shadow_saga_id",
        "kernel_message_id",
        "external_current_text",
        "external_intermediate_sent_marker",
        "visibility_policy",
        "discard_empty_completion",
        "visible_reply_committed",
        "discard_current_bubble",
        "rolling",
    )

    def __init__(self, store: RunDeliveryContextStore, run_id: str) -> None:
        self._store = store
        self._run_id = run_id

    def __getitem__(self, key: str) -> str:
        value = self._store.runtime_value(self._run_id, key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: str) -> None:
        self._store.set_runtime_value(self._run_id, key, value)

    def __delitem__(self, key: str) -> None:
        removed = self._store.pop_runtime_value(self._run_id, key)
        if removed is None:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        for key in self._static_keys:
            if self._store.runtime_value(self._run_id, key) is not None:
                yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)


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

    def runtime_view(self, run_id: str) -> RunDeliveryRuntimeView | None:
        """Return a dict-shaped runtime view backed by typed state."""

        if run_id not in self._contexts:
            return None
        return RunDeliveryRuntimeView(self, run_id)

    def runtime_value(self, run_id: str, key: str) -> str | None:
        """Read one observer-facing runtime value from typed state."""

        context = self._contexts[run_id]
        if key == "conversation_id":
            return context.conversation_id
        if key == "message_id":
            return context.message_id
        if key == "agent_id":
            return context.agent_id
        if key == "kernel_session_id":
            return context.kernel_session_id
        if key == "to_user_id":
            owner_direct = context.delivery_target.owner_direct
            return owner_direct.to_user_id if owner_direct is not None else ""
        if key == "trigger_source":
            return context.trigger_source or None
        if key == "reply_channel_name":
            return context.reply_channel_name or None
        if key == "reply_target_chat_id":
            return context.reply_target_chat_id or None
        if key == "reply_thread_id":
            return context.reply_thread_id or None
        if key == "feishu_message_id":
            return context.feishu_message_id or None
        if key == "shadow_saga_id":
            return context.shadow_saga_id or None
        if key == "kernel_message_id":
            return context.kernel_message_id or None
        if key == "external_current_text":
            return context.external_current_text or None
        if key == "external_intermediate_sent_marker":
            return context.external_intermediate_sent_marker or None
        if key == "visibility_policy":
            return context.visibility_policy.value
        if key == "discard_empty_completion":
            return "1" if context.discard_empty_completion else None
        if key == "visible_reply_committed":
            return "1" if context.visible_reply_committed else None
        if key == "discard_current_bubble":
            return "1" if context.discard_current_bubble else None
        if key == "rolling":
            return "1" if context.rolling else None
        raise KeyError(key)

    def set_runtime_value(self, run_id: str, key: str, value: str) -> None:
        """Write one observer-facing runtime value into typed state."""

        context = self._contexts[run_id]
        if key == "conversation_id":
            context.conversation_id = value
        elif key == "message_id":
            context.message_id = value
        elif key == "shadow_saga_id":
            context.shadow_saga_id = value
        elif key == "kernel_message_id":
            context.kernel_message_id = value
        elif key == "external_current_text":
            context.external_current_text = value
        elif key == "external_intermediate_sent_marker":
            context.external_intermediate_sent_marker = value
        elif key == "visible_reply_committed":
            context.visible_reply_committed = bool(value)
        elif key == "discard_current_bubble":
            context.discard_current_bubble = bool(value)
        elif key == "rolling":
            context.rolling = bool(value)
        else:
            raise KeyError(key)
        self._sync_legacy(run_id)

    def pop_runtime_value(self, run_id: str, key: str) -> str | None:
        """Clear one optional observer-facing runtime value from typed state."""

        existing = self.runtime_value(run_id, key)
        if key == "kernel_message_id":
            self._contexts[run_id].kernel_message_id = ""
        elif key == "external_current_text":
            self._contexts[run_id].external_current_text = ""
        elif key == "external_intermediate_sent_marker":
            self._contexts[run_id].external_intermediate_sent_marker = ""
        elif key == "visible_reply_committed":
            self._contexts[run_id].visible_reply_committed = False
        elif key == "discard_current_bubble":
            self._contexts[run_id].discard_current_bubble = False
        elif key == "rolling":
            self._contexts[run_id].rolling = False
        else:
            raise KeyError(key)
        self._sync_legacy(run_id)
        return existing

    def set_message_id(self, run_id: str, message_id: str) -> None:
        """Backfill the IM message id returned by a turn_start ack."""

        self.set_runtime_value(run_id, "message_id", message_id)

    def set_conversation_id(self, run_id: str, conversation_id: str) -> None:
        """Backfill the resolved IM conversation id returned by a lazy turn_start."""

        self.set_runtime_value(run_id, "conversation_id", conversation_id)

    def set_kernel_message_id(self, run_id: str, kernel_message_id: str) -> None:
        """Track the kernel assistant message id that owns the current IM bubble."""

        self.set_runtime_value(run_id, "kernel_message_id", kernel_message_id)

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

    def discard(self, run_id: str) -> None:
        """Remove typed and legacy context for one run."""

        self._contexts.pop(run_id, None)
        self._legacy_contexts.pop(run_id, None)

    def seed(self, context: RunDeliveryContext) -> RunDeliveryContext:
        """Store one context without clobbering an already-live run."""

        existing = self._contexts.get(context.run_id)
        if existing is not None:
            return existing
        context.ensure_initial_runtime_state()
        self._contexts[context.run_id] = context
        self._sync_legacy(context.run_id)
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

    def _sync_legacy(self, run_id: str) -> None:
        context = self._contexts.get(run_id)
        if context is not None:
            self._legacy_contexts[run_id] = context.to_legacy_dict()
