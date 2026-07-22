"""Route Gateway inbound messages into the per-session run coordinator."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import logging
from types import MappingProxyType
from typing import Protocol

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    PipelineResult,
    StopRunRequest,
    build_group_context_key,
)
from personal_assistant.gateway.runtime_protocol import (
    ShadowConversationRef,
    attach_runtime_protocol,
    external_identity_from_message,
    runtime_protocol_or_derive,
)
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.shadow_sync import ShadowSyncPendingError


class ShadowConversationSync(Protocol):
    """Write best-effort IM shadow messages for external-channel inbound."""

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> ShadowConversationRef | None:
        """Persist one inbound user message and return its durable IM anchor."""


@dataclass(frozen=True, slots=True)
class InboundRouteConfig:
    """Hold immutable channel/default routing values for the inbound facade.

    Args:
        channel_bindings: Mapping of ``channel:chat`` to default Agent id.
        default_agent_id: Node fallback when no explicit or bound Agent exists.
    """

    channel_bindings: Mapping[str, str] = field(default_factory=dict)
    default_agent_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "channel_bindings",
            MappingProxyType(dict(self.channel_bindings)),
        )


class InboundPipeline:
    """Apply route, group gate, shadow sync, and coordinator delegation.

    Args:
        agent_catalog: Shared live Agent snapshot owner used at the route boundary.
        run_coordinator: Sole owner of session/run/media/subscriber state.
        group_context_store: Optional ignored-group-chatter persistence owner.
        route_config: Immutable channel binding and default Agent values.
        shadow_sync: Optional best-effort external-to-IM shadow adapter.

    Notes:
        Group mention gating happens before session allocation. This facade owns no
        state that survives a message beyond its route configuration and references
        to the concrete downstream owners.
    """

    def __init__(
        self,
        *,
        agent_catalog: LiveAgentCatalog,
        run_coordinator: SessionRunCoordinator,
        group_context_store: GroupContextStore | None = None,
        route_config: InboundRouteConfig | None = None,
        shadow_sync: ShadowConversationSync | None = None,
    ) -> None:
        self._agent_catalog = agent_catalog
        self._run_coordinator = run_coordinator
        self._group_context_store = group_context_store
        self._route_config = route_config or InboundRouteConfig()
        self._shadow_sync = shadow_sync

    def seal(self) -> None:
        """Synchronously close coordinator admission."""

        self._run_coordinator.seal()

    async def settle_admission(self, deadline: float) -> None:
        """Wait for coordinator submit-or-rollback boundaries by one deadline."""

        await self._run_coordinator.settle_admission(deadline)

    async def handle_inbound(self, message: InboundMessage) -> PipelineResult | None:
        """Route one channel message or suppress unaddressed group chatter.

        Args:
            message: Normalized channel message.

        Returns:
            Coordinator result, or ``None`` when route/gating suppresses execution.
        """

        agent_id = self._resolve_agent(message)
        agent = self._agent_catalog.require(agent_id)
        should_process = self._should_process(
            message, agent_id=agent_id, agent_config=agent.config
        )
        sender_label = _resolve_sender_label(message)
        sync_only = message.metadata.get("sync_only") is True
        message = await self._sync_external_shadow_message(message, agent_id=agent_id)

        if message.is_group and self._group_context_store is not None:
            if sync_only or not should_process:
                self._group_context_store.append(
                    build_group_context_key(message, agent_id),
                    message.text,
                    sender=sender_label,
                )
        if sync_only or not should_process:
            return None

        session_key = build_session_key(message, agent_id=agent_id)
        if self._is_stop_command(message, agent_id=agent_id):
            return await self._run_coordinator.stop(
                StopRunRequest(
                    message=message,
                    agent=agent,
                    session_key=session_key,
                )
            )
        return await self._run_coordinator.dispatch(
            InboundRunRequest(
                message=message,
                agent=agent,
                session_key=session_key,
                sender_label=sender_label,
            )
        )

    async def _sync_external_shadow_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> InboundMessage:
        sync = self._shadow_sync
        external_identity = external_identity_from_message(message)
        if sync is None or message.channel_name == "web_relay":
            return message
        if external_identity is not None and external_identity.trigger_source == "im":
            return message
        try:
            shadow_ref = await sync.sync_user_message(message, agent_id=agent_id)
        except ShadowSyncPendingError as exc:
            logging.getLogger(__name__).warning(
                "external shadow anchor pending channel=%s chat=%s agent=%s: %s",
                message.channel_name,
                message.external_chat_id,
                agent_id,
                exc,
            )
            protocol = runtime_protocol_or_derive(message)
            return attach_runtime_protocol(
                message,
                replace(protocol, shadow_saga_id=exc.saga_id),
            )
        if shadow_ref is None:
            return message
        protocol = runtime_protocol_or_derive(message)
        enriched = replace(
            message,
            metadata={
                **message.metadata,
                "shadow_conversation_id": shadow_ref.conversation_id,
                "message_id": shadow_ref.im_message_id,
            },
        )
        return attach_runtime_protocol(
            enriched,
            replace(
                protocol,
                shadow_saga_id=shadow_ref.shadow_saga_id,
                shadow_ref=shadow_ref,
                im_message_id=shadow_ref.im_message_id,
            ),
        )

    def _resolve_agent(self, message: InboundMessage) -> str:
        metadata = message.metadata
        if message.is_group and message.agent_id:
            return self._require_known_agent(message.agent_id)
        if message.is_group:
            mentioned = metadata.get("mentioned_agent_ids")
            if isinstance(mentioned, list):
                for candidate in mentioned:
                    if (
                        isinstance(candidate, str)
                        and self._agent_catalog.get(candidate) is not None
                    ):
                        return candidate
            reply_to_agent_id = metadata.get("reply_to_agent_id")
            if (
                isinstance(reply_to_agent_id, str)
                and self._agent_catalog.get(reply_to_agent_id) is not None
            ):
                return reply_to_agent_id
        if message.agent_id:
            return self._require_known_agent(message.agent_id)
        bound = self._route_config.channel_bindings.get(
            f"{message.channel_name}:{message.external_chat_id}"
        )
        if bound is not None:
            return self._require_known_agent(bound)
        if self._route_config.default_agent_id is not None:
            return self._require_known_agent(self._route_config.default_agent_id)
        snapshots = self._agent_catalog.values_snapshot()
        if not snapshots:
            raise LookupError("no default agent configured")
        return snapshots[0].agent_id

    def _require_known_agent(self, agent_id: str) -> str:
        if self._agent_catalog.get(agent_id) is None:
            raise LookupError(f"unknown agent_id: {agent_id}")
        return agent_id

    @staticmethod
    def _should_process(
        message: InboundMessage,
        *,
        agent_id: str,
        agent_config: AgentWorkspaceConfig,
    ) -> bool:
        if not message.is_group:
            return True
        if message.text.strip() == "/stop":
            return True
        if (agent_config.group_reply_policy or "MENTION").upper() == "ALWAYS":
            return True
        mentioned = message.metadata.get("mentioned_agent_ids")
        if isinstance(mentioned, list) and agent_id in mentioned:
            return True
        reply_to = message.metadata.get("reply_to_agent_id")
        if isinstance(reply_to, str) and reply_to.strip() == agent_id:
            return True
        return f"@{agent_id}" in message.text

    @staticmethod
    def _is_stop_command(message: InboundMessage, *, agent_id: str) -> bool:
        text = message.text.strip()
        if text == "/stop":
            return True
        mentioned = message.metadata.get("mentioned_agent_ids")
        structurally_mentioned = isinstance(mentioned, list) and agent_id in mentioned
        reply_to = message.metadata.get("reply_to_agent_id")
        structurally_mentioned = structurally_mentioned or (
            isinstance(reply_to, str) and reply_to.strip() == agent_id
        )
        if not structurally_mentioned:
            return text.replace(f"@{agent_id}", "").strip() == "/stop"
        candidates = {f"@{agent_id}"}
        feishu_mentions = message.metadata.get("feishu_mentions")
        if isinstance(feishu_mentions, list):
            for mention in feishu_mentions:
                if not isinstance(mention, Mapping):
                    continue
                for key in ("name", "key"):
                    value = mention.get(key)
                    if isinstance(value, str) and value.strip():
                        raw = value.strip()
                        candidates.add(raw)
                        candidates.add(raw if raw.startswith("@") else f"@{raw}")
        normalized = text
        for mention in sorted(candidates, key=len, reverse=True):
            normalized = normalized.replace(mention, " ")
        return " ".join(normalized.split()) == "/stop"


def _resolve_sender_label(message: InboundMessage) -> str:
    display_name = message.metadata.get("sender_display_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    sender_name = message.metadata.get("sender_name")
    if isinstance(sender_name, str) and sender_name.strip():
        return sender_name.strip()
    return message.external_user_id
