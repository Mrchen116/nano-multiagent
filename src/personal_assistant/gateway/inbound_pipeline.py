"""Inbound four-step decision pipeline for Node Gateway channel messages."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from typing import Literal

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
        outbound: Normalized outbound payload returned by the outbound router, or ``None``
            when group-chat NO_REPLY suppresses user-visible delivery.
    """

    agent_id: str
    session_key: str
    kernel_session_id: str
    run_id: str
    reply_text: str
    outbound: OutboundMessage | None


@dataclass(frozen=True, slots=True)
class RelayLifecycleUpdate:
    """Describe one relay-visible execution milestone emitted by the pipeline."""

    phase: Literal["accepted", "running", "completed", "failed"]
    agent_id: str
    session_key: str
    run_id: str | None = None
    reply_text: str | None = None
    error: str | None = None
    detail: Mapping[str, Any] | None = None


RelayLifecycleCallback = Callable[[InboundMessage, RelayLifecycleUpdate], Awaitable[None]]

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
_EVENT_POLL_MAX_EVENTS = 200
_EVENT_POLL_TIMEOUT_SECONDS = 0.25


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
        relay_lifecycle_callback: Optional async hook that mirrors relay execution milestones
            back to IM-facing runtime wiring.

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
        relay_lifecycle_callback: RelayLifecycleCallback | None = None,
    ) -> None:
        self._kernel_client = kernel_client
        self._agents = {agent.agent_id: agent for agent in agents}
        self._outbound_router = outbound_router
        self._run_queue = run_queue
        self._session_store = session_store
        self._channel_bindings = dict(channel_bindings or {})
        self._default_agent_id = default_agent_id or (agents[0].agent_id if agents else None)
        self._relay_lifecycle_callback = relay_lifecycle_callback

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
            run_id: str | None = None
            try:
                binding = self._ensure_binding(message, agent_id=agent_id, session_key=session_key)
                run_payload = self._kernel_client.send_message_async(
                    session_id=binding.kernel_session_id,
                    text=message.text,
                )
                run_id = str(run_payload.get("run_id", "")).strip()
                await self._emit_relay_lifecycle(
                    message,
                    RelayLifecycleUpdate(
                        phase="accepted",
                        agent_id=agent_id,
                        session_key=session_key,
                        run_id=run_id or None,
                    ),
                )
                run_state, reply_text = self._await_terminal_run(
                    kernel_session_id=binding.kernel_session_id,
                    run_id=run_id,
                )
                await self._emit_relay_lifecycle(
                    message,
                    RelayLifecycleUpdate(
                        phase="running",
                        agent_id=agent_id,
                        session_key=session_key,
                        run_id=run_id or None,
                        reply_text=reply_text,
                    ),
                )
                outbound: OutboundMessage | None = None
                lifecycle_detail: Mapping[str, Any] | None = None
                if not self._should_suppress_no_reply(message, reply_text=reply_text):
                    outbound = self._outbound_router.send_text(text=reply_text, reply_context=binding.reply_context)
                else:
                    lifecycle_detail = {"suppressed_by": "no_reply_token"}
                result = PipelineResult(
                    agent_id=agent_id,
                    session_key=session_key,
                    kernel_session_id=binding.kernel_session_id,
                    run_id=run_id,
                    reply_text=reply_text,
                    outbound=outbound,
                )
                await self._emit_relay_lifecycle(
                    message,
                    RelayLifecycleUpdate(
                        phase="completed",
                        agent_id=agent_id,
                        session_key=session_key,
                        run_id=run_id or None,
                        reply_text=reply_text,
                        detail=lifecycle_detail,
                    ),
                )
                return result
            except Exception as exc:
                await self._emit_relay_lifecycle(
                    message,
                    RelayLifecycleUpdate(
                        phase="failed",
                        agent_id=agent_id,
                        session_key=session_key,
                        run_id=run_id,
                        error=str(exc),
                    ),
                )
                raise

        return await self._run_queue.submit(session_key, _run)

    async def _emit_relay_lifecycle(self, message: InboundMessage, update: RelayLifecycleUpdate) -> None:
        callback = self._relay_lifecycle_callback
        if callback is None:
            return
        await callback(message, update)

    def _resolve_agent(self, message: InboundMessage) -> str:
        if message.agent_id:
            return self._require_known_agent(message.agent_id)
        metadata = dict(message.metadata)
        mentioned = metadata.get("mentioned_agent_ids")
        if isinstance(mentioned, list):
            for candidate in mentioned:
                if isinstance(candidate, str) and candidate in self._agents:
                    return self._require_known_agent(candidate)
        reply_to_agent_id = metadata.get("reply_to_agent_id")
        if isinstance(reply_to_agent_id, str) and reply_to_agent_id in self._agents:
            return self._require_known_agent(reply_to_agent_id)
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

    @staticmethod
    def _is_no_reply_token(text: str) -> bool:
        return text.strip() == "NO_REPLY"

    @classmethod
    def _should_suppress_no_reply(cls, message: InboundMessage, *, reply_text: str) -> bool:
        return message.is_group and cls._is_no_reply_token(reply_text)

    def _require_known_agent(self, agent_id: str) -> str:
        if agent_id not in self._agents:
            raise LookupError(f"unknown agent_id: {agent_id}")
        return agent_id

    def _await_terminal_run(self, *, kernel_session_id: str, run_id: str) -> tuple[Mapping[str, object], str]:
        stream_session_events = getattr(self._kernel_client, "stream_session_events", None)
        if not callable(stream_session_events):
            run_state = self._kernel_client.get_run(run_id=run_id)
            status = self._run_status(run_state)
            if status in _TERMINAL_RUN_STATUSES and status != "completed":
                raise RuntimeError(self._extract_run_error(run_state, fallback_status=status))
            return run_state, self._extract_reply_text(run_state)

        reply_text = ""
        seen_event_ids: set[str] = set()
        seen_event_fingerprints: set[str] = set()
        while True:
            events = stream_session_events(
                session_id=kernel_session_id,
                max_events=_EVENT_POLL_MAX_EVENTS,
                timeout_seconds=_EVENT_POLL_TIMEOUT_SECONDS,
            )
            reply_text = self._merge_reply_text_from_events(
                events,
                run_id=run_id,
                current=reply_text,
                seen_event_ids=seen_event_ids,
                seen_event_fingerprints=seen_event_fingerprints,
            )
            run_state = self._kernel_client.get_run(run_id=run_id)
            status = self._run_status(run_state)
            if status not in _TERMINAL_RUN_STATUSES:
                continue
            if status != "completed":
                raise RuntimeError(self._extract_run_error(run_state, fallback_status=status))
            return run_state, self._extract_reply_text(run_state, streamed_text=reply_text)

    @staticmethod
    def _merge_reply_text_from_events(
        events: list[dict[str, object]],
        *,
        run_id: str,
        current: str,
        seen_event_ids: set[str],
        seen_event_fingerprints: set[str],
    ) -> str:
        reply_text = current
        for event in events:
            data = event.get("data")
            if not isinstance(data, dict) or data.get("run_id") != run_id:
                continue
            dedupe_key = InboundPipeline._event_dedupe_key(
                event,
                seen_event_ids=seen_event_ids,
                seen_event_fingerprints=seen_event_fingerprints,
            )
            if dedupe_key is None:
                continue
            if str(event.get("event", "")).strip() != "text_delta":
                continue
            delta = data.get("delta")
            if isinstance(delta, str) and delta:
                reply_text = InboundPipeline._merge_text_delta(reply_text, delta)
        return reply_text

    @staticmethod
    def _event_dedupe_key(
        event: Mapping[str, object],
        *,
        seen_event_ids: set[str],
        seen_event_fingerprints: set[str],
    ) -> str | None:
        event_id = event.get("id")
        if isinstance(event_id, str) and event_id.strip():
            normalized_event_id = event_id.strip()
            if normalized_event_id in seen_event_ids:
                return None
            seen_event_ids.add(normalized_event_id)
            return normalized_event_id
        fingerprint = json.dumps(event, sort_keys=True, ensure_ascii=False)
        if fingerprint in seen_event_fingerprints:
            return None
        seen_event_fingerprints.add(fingerprint)
        return fingerprint

    @staticmethod
    def _run_status(run_state: Mapping[str, object]) -> str:
        return str(run_state.get("status", "")).strip().lower()

    @staticmethod
    def _extract_run_error(run_state: Mapping[str, object], *, fallback_status: str) -> str:
        error = run_state.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
        if isinstance(error, Mapping):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return f"kernel run ended with status={fallback_status}"

    @staticmethod
    def _merge_text_delta(current: str, delta: str) -> str:
        if not current:
            return delta
        if delta.startswith(current):
            return delta
        return f"{current}{delta}"

    @staticmethod
    def _extract_reply_text(run_state: Mapping[str, object], *, streamed_text: str = "") -> str:
        output_text = run_state.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        if streamed_text.strip():
            return streamed_text.strip()
        error = run_state.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
        return ""
