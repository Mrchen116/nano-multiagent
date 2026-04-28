"""Inbound four-step decision pipeline for Node Gateway channel messages."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from typing import Literal

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.client.kernel_api_client import KernelApiClient
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.group_context_store import GroupContextStore
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
    usage: Mapping[str, int] | None = None


RelayLifecycleCallback = Callable[[InboundMessage, RelayLifecycleUpdate], Awaitable[None]]

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
# Default port for the Gateway's internal HTTP dispatch endpoint.
_DEFAULT_GATEWAY_INTERNAL_PORT = 8089


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
        gateway_internal_port: Port for the Gateway's internal HTTP dispatch endpoint
            (``POST /internal/dispatch``).  Injected into kernel session metadata as
            ``gateway_dispatch_url`` so product tools (e.g. ``send_message``) can post
            outbound messages back through the Gateway without a separate discovery step.

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
        group_context_store: GroupContextStore | None = None,
        gateway_internal_port: int = _DEFAULT_GATEWAY_INTERNAL_PORT,
    ) -> None:
        self._kernel_client = kernel_client
        self._agents = {agent.agent_id: agent for agent in agents}
        self._outbound_router = outbound_router
        self._run_queue = run_queue
        self._session_store = session_store
        self._channel_bindings = dict(channel_bindings or {})
        self._default_agent_id = default_agent_id or (agents[0].agent_id if agents else None)
        self._relay_lifecycle_callback = relay_lifecycle_callback
        self._group_context_store = group_context_store
        self._gateway_internal_port = gateway_internal_port
        self._active_runs: dict[str, str] = {}
        self._active_runs_lock = asyncio.Lock()

    async def handle_inbound(self, message: InboundMessage) -> PipelineResult | None:
        """Process one inbound message through route, session, queue, and reply steps.

        Returns:
            The observable pipeline result when the message is allowed to run, or
            ``None`` when group-chat mention gating suppresses execution.
        """

        agent_id = self._resolve_agent(message)
        agent_config = self._agents.get(agent_id)
        should_process = self._should_process(message, agent_id=agent_id, agent_config=agent_config)

        # M247: prefer sender_display_name from relay metadata over raw external_user_id (UUID).
        # Relay metadata supplies display_name when the IM service could resolve it.
        # Fallback to external_user_id ensures pre-M247 payloads still get the UUID prefix.
        sender_label = _resolve_sender_label(message)

        if message.is_group and self._group_context_store is not None:
            if not should_process:
                # This relay's agent is not addressed — buffer message as background context
                # for this agent's own future turn.  Each agent receives its own relay from IM,
                # so we only write to this agent's buffer key (no cross-agent fan-out).
                # Store sender label (display_name or UUID) for [sender] text prefixes.
                self._group_context_store.append(
                    self._group_buf_key_for_agent(message, agent_id),
                    message.text,
                    sender=sender_label,
                )

        if not should_process:
            return None
        session_key = build_session_key(message, agent_id=agent_id)

        if self._is_stop_command(message, agent_id=agent_id):
            return await self._handle_stop_command(message, agent_id=agent_id, session_key=session_key)

        async def _run() -> PipelineResult:
            run_id: str | None = None
            try:
                binding = self._ensure_binding(message, agent_id=agent_id, session_key=session_key)
                buf_key = self._group_buf_key_for_agent(message, agent_id)
                # drain() returns (sender, text) tuples since M246; format each as "[sender] text"
                # so the kernel receives sender-prefixed, independently-structured context messages.
                buffered_pairs: list[tuple[str, str]] = (
                    self._group_context_store.drain(buf_key)
                    if message.is_group and self._group_context_store
                    else []
                )
                buffered_texts = [_format_sender_text(sender, text) for sender, text in buffered_pairs]
                # Group messages get a sender prefix so the kernel can identify who spoke.
                # Direct messages remain unchanged — no sender prefix needed.
                if message.is_group:
                    current_text = _format_sender_text(sender_label, message.text)
                else:
                    current_text = message.text
                texts = buffered_texts + [current_text]
                attachments = message.metadata.get("attachments")
                image_urls: list[dict[str, Any]] | None = None
                if isinstance(attachments, list) and attachments:
                    image_urls = [
                        item for item in attachments
                        if isinstance(item, dict) and isinstance(item.get("url"), str)
                    ] or None
                run_payload = self._kernel_client.submit_message(
                    session_id=binding.kernel_session_id,
                    texts=texts,
                    image_urls=image_urls,
                )
                run_id = str(run_payload.get("run_id", "")).strip()
                if run_id:
                    async with self._active_runs_lock:
                        self._active_runs[session_key] = run_id
                await self._emit_relay_lifecycle(
                    message,
                    RelayLifecycleUpdate(
                        phase="accepted",
                        agent_id=agent_id,
                        session_key=session_key,
                        run_id=run_id or None,
                    ),
                )
                async def _on_other_event(event: Mapping[str, object]) -> None:
                    origin = event.get("origin")
                    if origin == "user" or not origin:
                        return
                    event_name = event.get("event")
                    if event_name == "assistant_message":
                        content = event.get("content")
                        if isinstance(content, str) and content.strip():
                            self._outbound_router.send_text(text=content.strip(), reply_context=binding.reply_context)

                run_state, reply_text = await self._await_terminal_run_async(
                    kernel_session_id=binding.kernel_session_id,
                    run_id=run_id,
                    on_other=_on_other_event,
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
                        usage=self._extract_usage(run_state),
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
            finally:
                if run_id:
                    async with self._active_runs_lock:
                        if self._active_runs.get(session_key) == run_id:
                            self._active_runs.pop(session_key, None)

        return await self._run_queue.submit(session_key, _run)

    @staticmethod
    def _group_buf_key_for_agent(message: InboundMessage, agent_id: str) -> str:
        return f"{agent_id}:{message.channel_name}:{message.external_chat_id}"

    async def _emit_relay_lifecycle(self, message: InboundMessage, update: RelayLifecycleUpdate) -> None:
        callback = self._relay_lifecycle_callback
        if callback is None:
            return
        await callback(message, update)

    def _resolve_agent(self, message: InboundMessage) -> str:
        metadata = dict(message.metadata)
        if message.is_group and message.agent_id:
            return self._require_known_agent(message.agent_id)
        if message.is_group:
            mentioned = metadata.get("mentioned_agent_ids")
            if isinstance(mentioned, list):
                for candidate in mentioned:
                    if isinstance(candidate, str) and candidate in self._agents:
                        return self._require_known_agent(candidate)
            reply_to_agent_id = metadata.get("reply_to_agent_id")
            if isinstance(reply_to_agent_id, str) and reply_to_agent_id in self._agents:
                return self._require_known_agent(reply_to_agent_id)
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
        agent = self._agents[agent_id]
        if existing is not None and self._binding_matches_workspace_root(
            existing.kernel_session_id,
            expected_workspace_root=str(agent.workspace_root),
        ):
            return self._session_store.bind(
                session_key=session_key,
                kernel_session_id=existing.kernel_session_id,
                reply_context=build_reply_context(message),
            )
        response = self._kernel_client.create_session(
            workspace_root=str(agent.workspace_root),
            product_id="personal_assistant",
            title=agent.title,
            metadata=self._build_session_metadata(message, agent_id=agent_id),
        )
        kernel_session_id = str(response.get("session_id", "")).strip()
        if not kernel_session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        return self._session_store.bind(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=build_reply_context(message),
        )

    def _build_session_metadata(self, message: InboundMessage, *, agent_id: str) -> dict[str, object] | None:
        """Build kernel session metadata from local agent config and message routing fields.

        Args:
            message: Inbound channel message carrying routing metadata (conversation_id, etc.).
            agent_id: Resolved agent whose local config supplies prompt/skills/tool_allowlist.

        Returns:
            Metadata dict for kernel session creation. Prompt-related fields come from the
            local AgentWorkspaceConfig; routing fields (conversation_id, config_profile_version)
            come from message metadata. Group-chat sessions additionally carry
            ``conversation_type``, ``participants``, ``participant_agent_ids``, and
            ``external_chat_id`` so that downstream hooks (e.g. before_agent_start) can
            inject group context into the system prompt without requiring a separate API call.
        """

        agent = self._agents[agent_id]
        metadata = dict(message.metadata)
        session_metadata: dict[str, object] = {
            "agent_id": agent_id,
            # Inject internal Gateway dispatch URL so product tools (e.g. send_message)
            # can post outbound messages back through the Gateway HTTP boundary.
            "gateway_dispatch_url": f"http://127.0.0.1:{self._gateway_internal_port}/internal/dispatch",
        }
        conversation_id = metadata.get("conversation_id")
        if isinstance(conversation_id, str) and conversation_id.strip():
            session_metadata["conversation_id"] = conversation_id.strip()
        profile_version = metadata.get("config_profile_version")
        if isinstance(profile_version, int):
            session_metadata["config_profile_version"] = profile_version
        # Prompt/skills/tool_allowlist: read from local agent config, not message metadata.
        if agent.system_prompt:
            session_metadata["system_prompt"] = agent.system_prompt
        if agent.skills:
            session_metadata["skills"] = list(agent.skills)
        if agent.tool_allowlist:
            session_metadata["tool_allowlist"] = list(agent.tool_allowlist)
        # SPEC §7: inject group chat routing context into session metadata so the
        # before_agent_start hook can append a communication context block.
        if message.is_group:
            session_metadata["conversation_type"] = "group"
            session_metadata["external_chat_id"] = message.external_chat_id or ""
            # Prefer structured participants and normalize to actor-first identities.
            raw_participants = metadata.get("participants")
            normalized_participants = _normalize_group_participants(raw_participants)
            if normalized_participants:
                session_metadata["participants"] = normalized_participants
            participant_agent_ids = metadata.get("participant_agent_ids")
            if isinstance(participant_agent_ids, list):
                session_metadata["participant_agent_ids"] = [
                    str(aid) for aid in participant_agent_ids if isinstance(aid, str)
                ]
            elif normalized_participants:
                session_metadata["participant_agent_ids"] = _extract_participant_agent_ids(normalized_participants)
            else:
                session_metadata["participant_agent_ids"] = [agent_id]
        else:
            session_metadata["conversation_type"] = "direct"
        return session_metadata

    @staticmethod
    @staticmethod
    def _should_process(
        message: InboundMessage,
        *,
        agent_id: str,
        agent_config: AgentWorkspaceConfig | None = None,
    ) -> bool:
        """Apply the group-chat reply gate before kernel execution.

        Notes:
            The gateway keeps this gate at the routing boundary so ignored group chatter
            never allocates kernel sessions or queue slots. Channels may provide either
            structured metadata or plain-text `@agent` mentions; both are accepted here.

            group_reply_policy values:
            - "ALWAYS" (or "always"): respond to every group message regardless of mention.
            - "MENTION" (or "mention_only", default): only respond when explicitly @mentioned.
        """

        if not message.is_group:
            return True
        metadata = dict(message.metadata)
        policy = (agent_config.group_reply_policy or "MENTION").upper() if agent_config else "MENTION"
        if policy == "ALWAYS":
            return True
        if metadata.get("background_context_only") is True:
            return False
        # MENTION policy: check explicit mention metadata or plain-text @agent
        mentioned = metadata.get("mentioned_agent_ids")
        if isinstance(mentioned, list) and agent_id in mentioned:
            return True
        reply_to_agent_id = metadata.get("reply_to_agent_id")
        if isinstance(reply_to_agent_id, str) and reply_to_agent_id.strip() == agent_id:
            return True
        return f"@{agent_id}" in message.text

    @staticmethod
    def _is_no_reply_token(text: str) -> bool:
        return text.strip() == "NO_REPLY"

    @classmethod
    def _should_suppress_no_reply(cls, message: InboundMessage, *, reply_text: str) -> bool:
        return message.is_group and cls._is_no_reply_token(reply_text)

    def _is_stop_command(self, message: InboundMessage, *, agent_id: str) -> bool:
        """Check whether the inbound message is a /stop control command.

        Supports ``/stop``, ``@agent /stop``, and ``/stop @agent`` forms.
        """
        text = message.text.strip()
        mention = f"@{agent_id}"
        text = text.replace(mention, "").strip()
        return text == "/stop"

    async def _handle_stop_command(
        self,
        message: InboundMessage,
        *,
        agent_id: str,
        session_key: str,
    ) -> PipelineResult:
        """Handle /stop: interrupt active run or return friendly no-op message."""
        active_run_id: str | None = None
        async with self._active_runs_lock:
            active_run_id = self._active_runs.get(session_key)

        binding = self._ensure_binding(message, agent_id=agent_id, session_key=session_key)

        if active_run_id is None:
            reply_text = "当前没有正在执行的操作。"
            outbound = self._outbound_router.send_text(text=reply_text, reply_context=binding.reply_context)
            return PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id="",
                reply_text=reply_text,
                outbound=outbound,
            )

        self._kernel_client.interrupt_session(session_id=binding.kernel_session_id)
        self._kernel_client.append_message(
            session_id=binding.kernel_session_id,
            role="user",
            content="用户发送了 /stop 命令，要求终止当前操作。",
        )
        reply_text = "已停止当前操作。"
        outbound = self._outbound_router.send_text(text=reply_text, reply_context=binding.reply_context)
        return PipelineResult(
            agent_id=agent_id,
            session_key=session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id=active_run_id,
            reply_text=reply_text,
            outbound=outbound,
        )

    def register_agent(self, agent: AgentWorkspaceConfig) -> None:
        """Add or replace one live agent workspace binding for future sessions."""
        self._agents[agent.agent_id] = agent
        if self._default_agent_id is None:
            self._default_agent_id = agent.agent_id

    def _binding_matches_workspace_root(self, session_id: str, *, expected_workspace_root: str) -> bool:
        """Return whether one bound kernel session carries the exact expected workspace metadata.

        Notes:
            This detects legacy direct-chat sessions created before workspace propagation was
            wired through `/v1/sessions`. Those sessions silently fall back to repo root even
            though the gateway now knows the agent workspace, so they must be refreshed once.
            Older test doubles may not implement session lookup yet; in that case we preserve
            the historical reuse behavior instead of breaking unrelated coverage.
        """

        get_session = getattr(self._kernel_client, "get_session", None)
        if not callable(get_session):
            return True
        try:
            session_payload = get_session(session_id=session_id)
        except RuntimeError:
            return False
        metadata = session_payload.get("metadata")
        if not isinstance(metadata, Mapping):
            return False
        workspace_root = metadata.get("workspace_root")
        return isinstance(workspace_root, str) and workspace_root.strip() == expected_workspace_root.strip()

    def drop_agent_sessions(self, agent_id: str) -> None:
        """Drop existing kernel-session bindings for one agent after config sync."""
        self._session_store.drop_agent(agent_id)

    def _require_known_agent(self, agent_id: str) -> str:
        if agent_id not in self._agents:
            raise LookupError(f"unknown agent_id: {agent_id}")
        return agent_id

    async def _await_terminal_run_async(
        self,
        *,
        kernel_session_id: str,
        run_id: str,
        on_other: Callable[[Mapping[str, object]], Awaitable[None] | None] | None = None,
    ) -> tuple[Mapping[str, object], str]:
        """Consume persistent SSE stream until terminal run_status for run_id.

        Non-target events are passed to ``on_other`` if provided.  This lets
        callers route background-task or heartbeat runs through the same
        session-key serial queue while the user run is in progress.
        """
        reply_text = ""
        run_state: Mapping[str, object] | None = None

        async for event in self._kernel_client.stream_session(session_id=kernel_session_id):
            if event.get("run_id") != run_id:
                if on_other is not None:
                    result = on_other(event)
                    if asyncio.iscoroutine(result):
                        await result
                continue
            event_name = event.get("event")
            if event_name == "assistant_message":
                content = event.get("content")
                if isinstance(content, str):
                    reply_text = content
            elif event_name == "run_status":
                status = event.get("status")
                if status in _TERMINAL_RUN_STATUSES:
                    run_state = event
                    if status != "completed":
                        raise RuntimeError(self._extract_run_error(event, fallback_status=status))
                    break

        if run_state is None:
            raise RuntimeError("stream ended without terminal run_status")

        return run_state, reply_text

    @staticmethod
    def _map_kernel_event_to_run_activity(event: Mapping[str, object]) -> str | None:
        """Map a kernel SSE event to the feat-336 Run Activity event name.

        Returns ``None`` for events that have no Run Activity equivalent.
        """
        event_name = event.get("event")
        if event_name == "run_status":
            status = event.get("status")
            if status == "running":
                return "agent.run.started"
            if status == "completed":
                return "agent.run.completed"
            if status in {"failed", "cancelled"}:
                return "agent.run.failed"
        if event_name == "assistant_message":
            return "agent.text.message"
        if event_name == "tool_start":
            return "agent.tool.started"
        if event_name == "tool_end":
            return "agent.tool.completed"
        return None

    @staticmethod
    def _run_status(run_state: Mapping[str, object]) -> str:
        status = str(run_state.get("status", "")).strip().lower()
        if status:
            return status
        output_text = run_state.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return "completed"
        error = run_state.get("error")
        if error is not None:
            return "failed"
        return ""

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

    @classmethod
    def _extract_reply_text(cls, run_state: Mapping[str, object], *, streamed_text: str = "") -> str:
        output_text = run_state.get("output_text")
        normalized_output = output_text.strip() if isinstance(output_text, str) else ""
        if cls._is_no_reply_token(normalized_output):
            return normalized_output
        if streamed_text.strip():
            return streamed_text.strip()
        if normalized_output:
            return normalized_output
        error = run_state.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
        return ""

    @staticmethod
    def _extract_usage(run_state: Mapping[str, object]) -> Mapping[str, int] | None:
        usage = run_state.get("usage")
        if not isinstance(usage, Mapping):
            return None
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
            return None
        if not isinstance(total_tokens, int):
            total_tokens = prompt_tokens + completion_tokens
        return {
            "prompt_tokens": max(prompt_tokens, 0),
            "completion_tokens": max(completion_tokens, 0),
            "total_tokens": max(total_tokens, 0),
        }


def _format_sender_text(sender: str, text: str) -> str:
    """Prepend ``[sender]`` prefix to a group message text.

    Args:
        sender: Display label for the sender (empty string when unknown).
        text: Raw message text.

    Returns:
        ``"[sender] text"`` when sender is non-empty, otherwise ``text`` unchanged.

    Notes:
        Gateway layer owns this formatting so the kernel remains sender-agnostic.
        The prefix follows the same convention described in Communication Context
        ``message_format`` so the LLM can parse sender identity from each message.
    """
    if sender:
        return f"[{sender}] {text}"
    return text


def _resolve_sender_label(message: "InboundMessage") -> str:
    """Return the best available display label for a message sender.

    Args:
        message: Inbound channel message carrying routing metadata.

    Returns:
        ``sender_display_name`` from metadata when present, otherwise
        ``external_user_id`` (fallback for pre-M247 relay payloads).

    Notes:
        M247 relay payloads include ``sender.display_name`` resolved by the IM
        service.  Older payloads omit the field; this function ensures the
        gateway falls back gracefully without querying IM.
    """
    display_name = message.metadata.get("sender_display_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    return message.external_user_id


def _normalize_group_participants(raw_participants: object) -> list[dict[str, str]]:
    """Normalize relay participants to actor-first user_id/agent_id identities."""
    if not isinstance(raw_participants, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in raw_participants:
        if not isinstance(item, Mapping):
            continue
        participant_type = _normalize_participant_type(item.get("type"))
        if participant_type is None:
            continue
        display_name = _optional_stripped_text(item.get("display_name"))
        if participant_type == "agent":
            agent_id = _optional_stripped_text(item.get("agent_id")) or _optional_stripped_text(item.get("id"))
            if agent_id is None:
                continue
            entry: dict[str, str] = {"type": "agent", "agent_id": agent_id}
        else:
            user_id = _optional_stripped_text(item.get("user_id")) or _optional_stripped_text(item.get("id"))
            if user_id is None:
                continue
            entry = {"type": "user", "user_id": user_id}
        if display_name is not None:
            entry["display_name"] = display_name
        normalized.append(entry)
    return normalized


def _extract_participant_agent_ids(participants: list[dict[str, str]]) -> list[str]:
    """Extract stable agent IDs from normalized participant entries."""
    seen: set[str] = set()
    agent_ids: list[str] = []
    for participant in participants:
        if participant.get("type") != "agent":
            continue
        agent_id = participant.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id.strip():
            continue
        normalized_id = agent_id.strip()
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        agent_ids.append(normalized_id)
    return agent_ids


def _normalize_participant_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"user", "agent"}:
        return normalized
    return None


def _optional_stripped_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
