"""Route Gateway inbound messages into the per-session run coordinator."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import logging
from types import MappingProxyType
from typing import Protocol

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_models import (
    CompactSessionRequest,
    GatewayShadowState,
    InboundRunRequest,
    NewSessionRequest,
    PipelineResult,
    RoutedInbound,
    StopRunRequest,
    WorkflowCommandRequest,
    build_group_context_key,
)
from personal_assistant.product import resolve_enabled_tools
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.shadow_sync import ShadowSyncPendingError


class ShadowConversationSync(Protocol):
    """Write best-effort IM shadow messages for external-channel inbound."""

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> GatewayShadowState:
        """Persist one inbound user message and return its Gateway shadow state."""


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
        normalized_command = self._normalize_command_text(message, agent_id=agent_id)
        command, focus = self._parse_control_command(normalized_command)
        should_process = self._should_process(
            message,
            agent_id=agent_id,
            agent_config=agent.config,
            control_command=command,
        )
        sender_label = _resolve_sender_label(message)
        sync_only = message.metadata.get("sync_only") is True
        session_key = build_session_key(message, agent_id=agent_id)
        compact_reservation = (
            self._run_coordinator.reserve_compact(
                session_key=session_key,
                agent_id=agent.agent_id,
            )
            if command == "compact" and not sync_only and should_process
            else None
        )
        try:
            shadow = await self._sync_external_shadow_message(
                message, agent_id=agent_id
            )
        except BaseException:
            if compact_reservation is not None:
                self._run_coordinator.abandon_compact(compact_reservation)
            raise

        if message.is_group and self._group_context_store is not None:
            if sync_only or not should_process:
                self._group_context_store.append(
                    build_group_context_key(message, agent_id),
                    message.text,
                    sender=sender_label,
                    metadata=_buffered_input_metadata(message.metadata),
                )
        if sync_only or not should_process:
            return None

        routed = RoutedInbound(message=message, shadow=shadow)
        if command == "stop":
            return await self._run_coordinator.stop(
                StopRunRequest(
                    routed=routed,
                    agent=agent,
                    session_key=session_key,
                )
            )
        if command == "new":
            return await self._run_coordinator.new_session(
                NewSessionRequest(
                    routed=routed,
                    agent=agent,
                    session_key=session_key,
                    operation_id=self._control_operation_id(routed),
                )
            )
        if command == "compact":
            assert compact_reservation is not None
            return await self._run_coordinator.commit_compact(
                compact_reservation,
                CompactSessionRequest(
                    routed=routed,
                    agent=agent,
                    session_key=session_key,
                    focus=focus,
                    operation_id=self._control_operation_id(routed),
                ),
            )
        if normalized_command.startswith("/") and "Workflow" in resolve_enabled_tools(
            agent.config
        ):
            workflow_result = await self._run_coordinator.workflow_command(
                WorkflowCommandRequest(
                    routed=routed,
                    agent=agent,
                    session_key=session_key,
                    command_text=normalized_command,
                    sender_label=sender_label,
                    operation_id=self._control_operation_id(routed),
                )
            )
            if workflow_result is not None:
                return workflow_result
        return await self._run_coordinator.dispatch(
            InboundRunRequest(
                routed=routed,
                agent=agent,
                session_key=session_key,
                sender_label=sender_label,
            )
        )

    async def _sync_external_shadow_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> GatewayShadowState:
        sync = self._shadow_sync
        external_identity = message.ingress.external_conversation
        if sync is None or message.ingress.im_relay is not None:
            return GatewayShadowState()
        if external_identity is not None and external_identity.trigger_source == "im":
            return GatewayShadowState()
        try:
            return await sync.sync_user_message(message, agent_id=agent_id)
        except ShadowSyncPendingError as exc:
            logging.getLogger(__name__).warning(
                "external shadow anchor pending channel=%s chat=%s agent=%s: %s",
                message.channel_name,
                message.external_chat_id,
                agent_id,
                exc,
            )
            return GatewayShadowState(saga_id=exc.saga_id)

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
        control_command: str | None = None,
    ) -> bool:
        if not message.is_group:
            return True
        if message.text.strip() == "/stop":
            return True
        # A web-relay external shadow historically synthesizes a target Agent when
        # relaying a group message without a mention. It remains valid for normal
        # conversational turns, but cannot authorize a destructive control.
        if (
            control_command in {"new", "compact"}
            and message.metadata.get("implicit_external_agent_target") is True
        ):
            reply_to = message.metadata.get("reply_to_agent_id")
            return isinstance(reply_to, str) and reply_to.strip() == agent_id
        mentioned = message.metadata.get("mentioned_agent_ids")
        has_mentioned_target = isinstance(mentioned, list) and any(
            isinstance(candidate, str) and candidate.strip() for candidate in mentioned
        )
        reply_to = message.metadata.get("reply_to_agent_id")
        has_reply_target = isinstance(reply_to, str) and bool(reply_to.strip())
        # Web IM group messages are relayed once per participant. Only an
        # unaddressed, exact `/new` is the explicit group-wide reset; a
        # reply/mention remains a targeted control even when its textual body is
        # just `/new`. External-channel groups retain their existing explicit
        # Bot-target requirement.
        if (
            control_command == "new"
            and message.text.strip() == "/new"
            and message.ingress.im_relay is not None
            and message.ingress.external_conversation is None
            and not has_mentioned_target
            and not has_reply_target
        ):
            return True
        # Controls other than the explicit group-wide `/new` require a concrete
        # target regardless of the Agent's normal group reply policy.
        if control_command in {"new", "compact"}:
            if isinstance(mentioned, list) and agent_id in mentioned:
                return True
            if has_reply_target and reply_to.strip() == agent_id:
                return True
            return f"@{agent_id}" in message.text
        if (agent_config.group_reply_policy or "MENTION").upper() == "ALWAYS":
            return True
        if isinstance(mentioned, list) and agent_id in mentioned:
            return True
        if has_reply_target and reply_to.strip() == agent_id:
            return True
        return f"@{agent_id}" in message.text

    @staticmethod
    def _normalize_command_text(message: InboundMessage, *, agent_id: str) -> str:
        """Strip structural mentions once for every shared slash-command parser.

        Mention stripping deliberately remains here at the shared inbound seam so
        Web IM and Feishu cannot acquire subtly different command grammars.
        """

        text = message.text.strip()
        mentioned = message.metadata.get("mentioned_agent_ids")
        structurally_mentioned = isinstance(mentioned, list) and agent_id in mentioned
        reply_to = message.metadata.get("reply_to_agent_id")
        structurally_mentioned = structurally_mentioned or (
            isinstance(reply_to, str) and reply_to.strip() == agent_id
        )
        candidates = {f"@{agent_id}"}
        if structurally_mentioned:
            candidates.add(f'<mention type="agent" target_id="{agent_id}"/>')
        feishu_mentions = message.metadata.get("feishu_mentions")
        if structurally_mentioned and isinstance(feishu_mentions, list):
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
        normalized = " ".join(normalized.split())
        return normalized

    @staticmethod
    def _parse_control_command(normalized: str) -> tuple[str | None, str | None]:
        """Return one exact built-in control command and optional compact focus."""

        if normalized == "/stop":
            return "stop", None
        if normalized == "/new":
            return "new", None
        if normalized == "/compact":
            return "compact", None
        if normalized.startswith("/compact "):
            focus = normalized[len("/compact ") :].strip()
            if focus:
                return "compact", focus
        return None, None

    @staticmethod
    def _control_operation_id(routed: RoutedInbound) -> str | None:
        """Return the durable ingress identity usable for a replay-safe control."""

        if routed.shadow.saga_id:
            return f"shadow:{routed.shadow.saga_id}"
        relay = routed.message.ingress.im_relay
        if relay is None:
            return None
        for prefix, value in (
            ("relay", relay.relay_task_id),
            ("relay", relay.idempotency_key),
        ):
            if value:
                return f"{prefix}:{value}"
        return None


def _resolve_sender_label(message: InboundMessage) -> str:
    display_name = message.metadata.get("sender_display_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    sender_name = message.metadata.get("sender_name")
    if isinstance(sender_name, str) and sender_name.strip():
        return sender_name.strip()
    return message.external_user_id


def _buffered_input_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Retain only fields needed to reconstruct buffered Kernel input."""

    return {
        key: metadata[key]
        for key in (
            "attachments",
            "kernel_input_parts",
            "image_resolution_failure",
        )
        if key in metadata
    }
