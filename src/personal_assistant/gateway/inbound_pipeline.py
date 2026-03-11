"""Inbound four-step decision pipeline for Node Gateway channel messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.client.kernel_api_client import KernelApiClient
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import (
    SessionBinding,
    SessionBindingStore,
    build_reply_context,
    build_session_key,
    session_binding_store,
)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Expose observable outputs from one inbound pipeline execution.

    Args:
        agent_id: Routed agent chosen in step 1.
        session_key: Canonical gateway-local session key from step 2.
        kernel_session_id: Kernel session bound to the message.
        run_id: Async kernel run id created for the message.
        reply_text: Final reply text selected for outbound routing.
        outbound: Normalized outbound payload returned by the outbound router.
    """

    agent_id: str
    session_key: str
    kernel_session_id: str
    run_id: str
    reply_text: str
    outbound: OutboundMessage


class InboundPipeline:
    """Execute the NodeGateway-SPEC §4 four-step decision flow.

    Args:
        kernel_client: HTTP boundary used to create sessions and dispatch runs.
        agents: Managed agent workspace configs indexed by agent id.
        outbound_router: Router used for step 4 reply delivery.
        run_queue: Per-session FIFO queue manager used for step 3.
        session_store: Local session binding store used to persist key → kernel session.
        channel_bindings: Optional ``channel:chat`` default-agent bindings.
        default_agent_id: Node-level fallback agent used when no explicit/bound agent matches.

    Notes:
        Group-chat traffic honors the NodeGateway-SPEC @mention gate before any kernel
        session or run is created. Only direct chats, explicit mentions, replies to the
        agent, or control-command triggers are allowed to proceed.
    """

    def __init__(
        self,
        *,
        kernel_client: KernelApiClient,
        agents: tuple[AgentWorkspaceConfig, ...],
        outbound_router: OutboundRouter,
        run_queue: SessionRunQueue,
        session_store: SessionBindingStore = session_binding_store,
        channel_bindings: Mapping[str, str] | None = None,
        default_agent_id: str | None = None,
    ) -> None:
        self._kernel_client = kernel_client
        self._agents = {agent.agent_id: agent for agent in agents}
        self._outbound_router = outbound_router
        self._run_queue = run_queue
        self._session_store = session_store
        self._channel_bindings = dict(channel_bindings or {})
        self._default_agent_id = default_agent_id or (agents[0].agent_id if agents else None)

    async def handle_inbound(self, message: InboundMessage) -> PipelineResult | None:
        """Process one inbound message through route, session, queue, and reply steps.

        Returns:
            The observable pipeline result when the message is allowed to run, or
            ``None`` when group-chat mention gating suppresses execution.
        """

        agent_id = self._resolve_agent(message)
        if not self._should_process(message, agent_id=agent_id):
            return None
        session_key = build_session_key(message, agent_id=agent_id)

        async def _run() -> PipelineResult:
            binding = self._ensure_binding(message, agent_id=agent_id, session_key=session_key)
            run_payload = self._kernel_client.send_message_async(
                session_id=binding.kernel_session_id,
                text=message.text,
            )
            run_id = str(run_payload.get("run_id", "")).strip()
            run_state = self._kernel_client.get_run(run_id=run_id)
            reply_text = self._extract_reply_text(run_state)
            outbound = self._outbound_router.send_text(text=reply_text, reply_context=binding.reply_context)
            return PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id=run_id,
                reply_text=reply_text,
                outbound=outbound,
            )

        return await self._run_queue.submit(session_key, _run)

    def _resolve_agent(self, message: InboundMessage) -> str:
        if message.agent_id:
            return self._require_known_agent(message.agent_id)
        binding_key = f"{message.channel_name}:{message.external_chat_id}"
        bound_agent = self._channel_bindings.get(binding_key)
        if bound_agent is not None:
            return self._require_known_agent(bound_agent)
        if self._default_agent_id is None:
            raise LookupError("no default agent configured")
        return self._require_known_agent(self._default_agent_id)

    def _ensure_binding(self, message: InboundMessage, *, agent_id: str, session_key: str) -> SessionBinding:
        existing = self._session_store.get(session_key)
        if existing is not None:
            return existing
        agent = self._agents[agent_id]
        response = self._kernel_client.create_session(
            workspace_root=str(agent.workspace_root),
            product_id="personal_assistant",
            title=agent.title,
        )
        kernel_session_id = str(response.get("session_id", "")).strip()
        if not kernel_session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        return self._session_store.bind(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=build_reply_context(message),
        )

    @staticmethod
    def _should_process(message: InboundMessage, *, agent_id: str) -> bool:
        """Apply the group-chat @mention gate before kernel execution.

        Notes:
            The gateway keeps this gate at the routing boundary so ignored group chatter
            never allocates kernel sessions or queue slots. Channels may provide either
            structured metadata or plain-text `@agent` mentions; both are accepted here.
        """

        if not message.is_group:
            return True
        metadata = dict(message.metadata)
        mentioned = metadata.get("mentioned_agent_ids")
        if isinstance(mentioned, list) and agent_id in mentioned:
            return True
        reply_to_agent_id = metadata.get("reply_to_agent_id")
        if isinstance(reply_to_agent_id, str) and reply_to_agent_id.strip() == agent_id:
            return True
        trigger = metadata.get("trigger")
        if isinstance(trigger, str) and trigger.strip() in {"command", "mention", "reply"}:
            return True
        return f"@{agent_id}" in message.text

    def _require_known_agent(self, agent_id: str) -> str:
        if agent_id not in self._agents:
            raise LookupError(f"unknown agent_id: {agent_id}")
        return agent_id

    @staticmethod
    def _extract_reply_text(run_state: Mapping[str, object]) -> str:
        output_text = run_state.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        error = run_state.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
        return ""
