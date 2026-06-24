"""Inbound four-step decision pipeline for Node Gateway channel messages."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from typing import Literal

from personal_assistant.channels.base import (
    InboundMessage,
    OutboundMessage,
    ReplyContext,
)
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    resolve_run_model,
)
from personal_assistant.gateway.background_session_events import (
    BackgroundSessionEventSubscriber,
)
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

from agent.sdk import TERMINAL_RUN_STATUSES, USER_INTERRUPT_RECOVERY_CONTENT

if TYPE_CHECKING:
    from agent.sdk.kernel import Kernel


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
    # Populated on "accepted" so downstream wiring (e.g. permission_response handler)
    # can reverse-lookup kernel session from run_id without re-resolving binding.
    kernel_session_id: str | None = None


RelayLifecycleCallback = Callable[
    [InboundMessage, RelayLifecycleUpdate], Awaitable[None]
]

_TERMINAL_RUN_STATUSES = TERMINAL_RUN_STATUSES
# Default port for the Gateway's internal HTTP dispatch endpoint.
_DEFAULT_GATEWAY_INTERNAL_PORT = 8089
# Keep the Gateway's run owner aligned with IM's relay watchdog. The timeout is
# idle-based: every kernel event resets it, so active long-running tool loops continue.
_DEFAULT_RUN_IDLE_TIMEOUT_SECONDS = 120.0


def resolve_effective_tool_allowlist(
    tool_allowlist: Sequence[str],
    *,
    default_tool_ids: Sequence[str],
) -> list[str] | None:
    """Resolve a per-session tool allowlist as a TRUE whitelist.

    feat-394 fix (supersedes M7 R5-2 force-merge): ``tool_allowlist`` is the user's
    explicit tool whitelist, not an additive extras list.

    - Non-empty ``tool_allowlist`` → exactly those tools. A user may select a subset
      of the product defaults, so default file/web tools CAN be disabled.
    - Empty ``tool_allowlist`` → the product default tool set (unconfigured agent).

    feat-394 M9 R4: ``cron_enabled`` param removed. The call-site reads
    ``agent.cron_enabled`` (@property from features dict) and appends ``"cron"``
    before passing the list here, keeping this function free of feature-model state.

    Args:
        tool_allowlist: The agent's stored explicit tool whitelist (may be empty).
            Call-site must append gated capabilities (e.g. ``"cron"``) before
            passing when the relevant feature flag is on.
        default_tool_ids: Product default tool ids used when the whitelist is empty.

    Returns:
        Explicit tool-id list for ``Kernel.create_session(tool_allowlist=...)``, or
        ``None`` only in the degenerate case of an empty resolved set.
    """
    effective = list(tool_allowlist) if tool_allowlist else list(default_tool_ids)
    return effective or None


class InboundPipeline:
    """Execute the gateway four-step inbound decision flow (see docs/specs/gateway/spec.md).

    Args:
        kernel: In-process Kernel SDK instance (refactor-387 M3+).
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
        run_idle_timeout_seconds: Maximum silence between kernel events before the
            active run is cancelled so the per-session FIFO can continue.

    Notes:
        Group-chat traffic honors the gateway @mention gate (see docs/specs/gateway/spec.md) before any kernel
        session or run is created. Only direct chats, explicit mentions, replies to the
        agent, or control-command triggers are allowed to proceed.
    """

    def __init__(
        self,
        *,
        kernel: "Kernel",
        agents: tuple[AgentWorkspaceConfig, ...],
        outbound_router: OutboundRouter,
        run_queue: SessionRunQueue,
        session_store: SessionBindingStore = session_binding_store,
        channel_bindings: Mapping[str, str] | None = None,
        default_agent_id: str | None = None,
        relay_lifecycle_callback: RelayLifecycleCallback | None = None,
        group_context_store: GroupContextStore | None = None,
        gateway_internal_port: int = _DEFAULT_GATEWAY_INTERNAL_PORT,
        run_idle_timeout_seconds: float = _DEFAULT_RUN_IDLE_TIMEOUT_SECONDS,
        kernel_event_observer: Callable[[Mapping[str, Any]], None] | None = None,
        session_event_callback: Callable[[str, Mapping[str, Any]], Awaitable[None]]
        | None = None,
        product_default_model: str | None = None,
    ) -> None:
        if run_idle_timeout_seconds <= 0:
            raise ValueError("run_idle_timeout_seconds must be > 0")
        self._kernel = kernel
        self._agents = {agent.agent_id: agent for agent in agents}
        # bugfix-429 决策2: the product owns the default model. Each turn submits
        # agent.default_model (read fresh from self._agents so a config change takes
        # effect on the next turn, incl. old sessions) and falls back to this
        # product default when the agent has not selected one. The kernel holds no
        # conversational default.
        self._product_default_model = product_default_model
        self._outbound_router = outbound_router
        self._run_queue = run_queue
        self._session_store = session_store
        self._channel_bindings = dict(channel_bindings or {})
        self._default_agent_id = default_agent_id or (
            agents[0].agent_id if agents else None
        )
        self._relay_lifecycle_callback = relay_lifecycle_callback
        self._group_context_store = group_context_store
        self._gateway_internal_port = gateway_internal_port
        self._run_idle_timeout_seconds = run_idle_timeout_seconds
        self._active_runs: dict[str, str] = {}
        self._active_runs_lock = asyncio.Lock()
        # bugfix-426-M3: serialize the group-buffer drain per session. The steer
        # fast-path's "has_active_run gate → _build_message_parts(drain)" span and
        # the normal path's drain (inside _run_turn, itself serialized by the
        # run_queue) both consume the SAME destructive group buffer. Without a
        # shared per-session lock two concurrent steers (or a steer racing the
        # normal path) interleave at the `await _ensure_binding` yield point and
        # split the buffered context — one drains everything, the other drains
        # nothing. This lock makes every drain for a session mutually exclusive;
        # it does NOT serialize the whole turn (the active run still receives the
        # injected steer), only the cheap gate+drain decision.
        self._session_drain_locks: dict[str, asyncio.Lock] = {}
        # bugfix-417-M5 (#114): run_ids stopped by an explicit user /stop, so the
        # terminal reconcile can attribute the in-flight tool card's content to the
        # user ("[Request interrupted by user for tool use]") instead of the generic
        # system-interrupt body. Bounded: entries are discarded on reconcile.
        self._user_interrupted_runs: set[str] = set()
        # feat-340-M2: bootstrap wires this to an IM event_bridge consumer so the browser
        # sees live tool_call / token_usage events; default None keeps pipeline product-agnostic.
        self._kernel_event_observer = kernel_event_observer
        # feat-349-M3: optional callback for session-level events (e.g. self_evolution_review)
        # that arrive after the main per-turn SSE loop has terminated.  Caller wires this to
        # send a system/meta notification to IM.  None keeps the pipeline IM-agnostic.
        self._session_event_callback = session_event_callback
        # bugfix-404-M3: async callable (text, reply_context, agent_id) → None that sends
        # a BACKGROUND_TASK run reply back to IM.  Wired by main.py after im_connection_manager
        # is created.  None disables BACKGROUND_TASK relay (outbound_router.send_text() is a
        # no-op for the web_relay channel, so this must be the real IM send path).
        self._bg_reply_sender: "Callable[[str, ReplyContext, str], Awaitable[None]] | None" = None
        # Tracks active BackgroundSessionEventSubscribers by kernel_session_id.
        self._bg_subscribers: dict[str, BackgroundSessionEventSubscriber] = {}

    async def handle_inbound(self, message: InboundMessage) -> PipelineResult | None:
        """Process one inbound message through route, session, queue, and reply steps.

        Returns:
            The observable pipeline result when the message is allowed to run, or
            ``None`` when group-chat mention gating suppresses execution.
        """

        agent_id = self._resolve_agent(message)
        agent_config = self._agents.get(agent_id)
        should_process = self._should_process(
            message, agent_id=agent_id, agent_config=agent_config
        )

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
            return await self._handle_stop_command(
                message, agent_id=agent_id, session_key=session_key
            )

        # Mid-run steer (bugfix-426 决策1): if a run is already active for this
        # session, inject this message into its next round instead of queueing a
        # new run behind it. The gateway-local _active_runs gate mirrors /stop's
        # cheap check; the parts are built once (drains the group buffer) and the
        # kernel atomically decides inject-vs-new. On injected=True we are done
        # (the active run's SSE stream surfaces the reply). On injected=False the
        # active run ended in the race window — hand the already-built parts to the
        # queued _run so the drained context is not lost (no re-drain).
        # bugfix-426-M3: hold the per-session drain lock across the WHOLE steer
        # decision — the has_active_run gate, _ensure_binding (a yield point), the
        # destructive _build_message_parts drain inside _try_steer_active_run, and
        # the atomic kernel steer submit. This is the span that previously let a
        # second concurrent steer cut in at the _ensure_binding await and split the
        # group buffer. The lock is shared with the normal-path drain (_run_turn),
        # so steer-vs-steer AND steer-vs-normal are both serialized; normal-vs-normal
        # is already serial via the run_queue. The fallback submit below runs OUTSIDE
        # the lock: it carries prebuilt_parts (no re-drain) and _run_turn would
        # otherwise re-acquire this same lock and self-deadlock.
        async with self._drain_lock_for(session_key):
            async with self._active_runs_lock:
                has_active_run = self._active_runs.get(session_key) is not None
            steered = (
                await self._try_steer_active_run(
                    message,
                    agent_id=agent_id,
                    session_key=session_key,
                    sender_label=sender_label,
                )
                if has_active_run
                else None
            )
        if has_active_run and steered is not None:
            injected_result, fallback_parts = steered
            if injected_result is not None:
                return injected_result
            return await self._run_queue.submit(
                session_key,
                lambda: self._run_turn(
                    message,
                    agent_id=agent_id,
                    session_key=session_key,
                    sender_label=sender_label,
                    prebuilt_parts=fallback_parts,
                ),
            )

        return await self._run_queue.submit(
            session_key,
            lambda: self._run_turn(
                message,
                agent_id=agent_id,
                session_key=session_key,
                sender_label=sender_label,
            ),
        )

    async def _try_steer_active_run(
        self,
        message: InboundMessage,
        *,
        agent_id: str,
        session_key: str,
        sender_label: str,
    ) -> tuple[PipelineResult | None, list[dict[str, Any]]] | None:
        """Attempt to inject this message into the session's active run.

        Returns:
            None when there is no bound/active run to steer (caller falls through
            to a normal queued run). Otherwise a ``(injected_result, parts)`` pair:
            ``injected_result`` is the PipelineResult when the kernel injected into
            the active run (caller returns it directly, no queued run); it is None
            when the active run ended in the race window, in which case ``parts``
            (already built, buffer drained) must be submitted by the caller's
            queued run instead of re-draining.
        """
        binding = await self._ensure_binding(
            message, agent_id=agent_id, session_key=session_key
        )
        parts = self._build_message_parts(
            message, agent_id=agent_id, sender_label=sender_label
        )
        agent_workspace_root_path = self._agents[agent_id].workspace_root
        run_record = self._kernel.submit(
            session_id=binding.kernel_session_id,
            parts=parts,
            workspace_root=agent_workspace_root_path,
            steer=True,
            model=self._resolve_model(agent_id),
        )
        if not getattr(run_record, "injected", False):
            # Race: run ended before the enqueue. Caller re-runs with these parts.
            return None, parts
        await self._emit_relay_lifecycle(
            message,
            RelayLifecycleUpdate(
                phase="accepted",
                agent_id=agent_id,
                session_key=session_key,
                run_id=run_record.run_id,
                kernel_session_id=binding.kernel_session_id,
            ),
        )
        # The injected message rides the active run's existing SSE stream — no new
        # _run_turn, no second event loop. Its reply surfaces through the run that
        # is already being consumed by the original turn's _run_turn.
        return (
            PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id=run_record.run_id,
                reply_text="",
                outbound=None,
            ),
            parts,
        )

    async def _run_turn(
        self,
        message: InboundMessage,
        *,
        agent_id: str,
        session_key: str,
        sender_label: str,
        prebuilt_parts: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        run_id: str | None = None
        try:
            binding = await self._ensure_binding(
                message, agent_id=agent_id, session_key=session_key
            )
            # Build parts once (drains the group buffer). The steer race path
            # passes already-built parts so the buffer is not drained twice.
            # bugfix-426-M3: hold the per-session drain lock around the drain so a
            # concurrent steer fast-path cannot interleave its own drain with this
            # one (the run_queue only serializes normal-vs-normal, not steer-vs-
            # normal). prebuilt_parts means the steer path already drained under the
            # lock, so we skip both the drain and the lock.
            if prebuilt_parts is not None:
                parts = prebuilt_parts
            else:
                async with self._drain_lock_for(session_key):
                    parts = self._build_message_parts(
                        message, agent_id=agent_id, sender_label=sender_label
                    )
            agent_workspace_root_path = self._agents[agent_id].workspace_root
            # submit() is sync, non-blocking — schedules the turn on RunsRegistry's
            # background loop and returns immediately with a RunRecord.
            run_record = self._kernel.submit(
                session_id=binding.kernel_session_id,
                parts=parts,
                workspace_root=agent_workspace_root_path,
                model=self._resolve_model(agent_id),
            )
            run_id = run_record.run_id
            # Anchor the per-turn event stream to this run's own start position.
            # Using 0 here would replay the ENTIRE in-memory session history every
            # turn, re-surfacing stale session-level events (e.g. self_evolution_review)
            # as if they were fresh — the source of the repeated "updated" notifications.
            anchor_sequence = run_record.start_sequence
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
                    kernel_session_id=binding.kernel_session_id,
                ),
            )

            async def _on_other_event(event: Mapping[str, object]) -> None:
                event_name = event.get("event")
                # Session-level events (e.g. self_evolution_review) are owned solely
                # by the persistent background subscriber started below, so they are
                # forwarded exactly once regardless of fork timing.  The main loop
                # deliberately ignores them here.
                origin = event.get("origin")
                if origin == "user" or not origin:
                    return
                if event_name == "assistant_message":
                    content = event.get("content")
                    if isinstance(content, str) and content.strip():
                        text = content.strip()
                        # bugfix-416 #107: fan-out (agent-to-agent) replies imply a
                        # group context; route through the shared guard so a NO_REPLY
                        # sentinel is suppressed here exactly like the main path.
                        if not self._should_suppress_no_reply(text, in_group=True):
                            self._outbound_router.send_text(
                                text=text,
                                reply_context=binding.reply_context,
                            )

            run_state, reply_text = await self._await_terminal_run_async(
                kernel_session_id=binding.kernel_session_id,
                run_id=run_id,
                anchor_sequence=anchor_sequence,
                on_other=_on_other_event,
            )
            # Start a persistent background subscriber for this session so that
            # self_evolution_review events and BACKGROUND_TASK run output published
            # after the main turn's SSE loop terminates still reach the PA gateway.
            # reply_context + session_key are passed so the subscriber can relay
            # BACKGROUND_TASK assistant_message events back to the originating IM
            # conversation via _bg_reply_sender (bugfix-404-M3).
            await self._ensure_background_subscriber(
                kernel_session_id=binding.kernel_session_id,
                last_sequence=anchor_sequence or 0,
                reply_context=binding.reply_context,
                session_key=session_key,
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
            # bugfix-417-fix2 (#114, Issue 1): a user-/stop-cancelled run is finalized
            # cleanly (above) but must NOT emit a final agent reply — the /stop handler
            # already replied "已停止当前操作。", and any partial streamed text is not a
            # complete answer. Suppress the reply send for cancelled; the bubble is
            # closed by the observer's terminal run_status handling.
            run_cancelled = run_state.get("status") == "cancelled"
            if run_cancelled:
                lifecycle_detail = {"suppressed_by": "cancelled"}
            elif not self._should_suppress_no_reply(
                reply_text, in_group=message.is_group
            ):
                outbound = self._outbound_router.send_text(
                    text=reply_text, reply_context=binding.reply_context
                )
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
                # bugfix-417-fix1 (B): clear the user-interrupt marker on EVERY
                # run terminal path. _emit_terminal_reconcile discards it when it
                # fires, but a run that ends without a reconcile (watchdog reap /
                # crash / normal completion of a non-/stop run) would otherwise
                # leak the entry forever. This finally is the single per-run
                # terminal chokepoint, so discarding here bounds the set.
                self._user_interrupted_runs.discard(run_id)

    @staticmethod
    def _group_buf_key_for_agent(message: InboundMessage, agent_id: str) -> str:
        return f"{agent_id}:{message.channel_name}:{message.external_chat_id}"

    def _drain_lock_for(self, session_key: str) -> asyncio.Lock:
        """Return the per-session lock guarding this session's group-buffer drain.

        bugfix-426-M3: lazily created so unbounded sessions do not preallocate
        locks. The same lock object is shared by the steer fast-path and the
        normal-path drain so the two are mutually exclusive (see __init__).
        """
        lock = self._session_drain_locks.get(session_key)
        if lock is None:
            lock = asyncio.Lock()
            self._session_drain_locks[session_key] = lock
        return lock

    def _build_message_parts(
        self, message: InboundMessage, *, agent_id: str, sender_label: str
    ) -> list[dict[str, Any]]:
        """Build the kernel input parts for one inbound message.

        Single source of truth for both the normal new-run path and the mid-run
        steer path so a steered message carries the SAME context as a queued one:
        drained group buffer (other speakers' messages, each ``[sender] text``),
        the current message with its own sender prefix in group chats, and image
        attachments. Steering must not collapse to a bare ``message.text`` —
        otherwise group runs would lose sender identity and buffered context
        (bugfix-426 决策1; non-goal: group behavior must not change).

        Side effect: drains this agent's group buffer (destructive). Call exactly
        once per delivered message; the caller passes the result to whichever path
        actually submits it.
        """
        buffered_pairs: list[tuple[str, str]] = (
            self._group_context_store.drain(
                self._group_buf_key_for_agent(message, agent_id)
            )
            if message.is_group and self._group_context_store
            else []
        )
        buffered_texts = [
            _format_sender_text(sender, text) for sender, text in buffered_pairs
        ]
        # Group messages get a sender prefix so the kernel can identify who spoke.
        # Direct messages remain unchanged — no sender prefix needed.
        if message.is_group:
            current_text = _format_sender_text(sender_label, message.text)
        else:
            current_text = message.text
        texts = buffered_texts + [current_text]
        parts: list[dict[str, Any]] = [{"type": "text", "text": t} for t in texts]
        attachments = message.metadata.get("attachments")
        if isinstance(attachments, list) and attachments:
            for item in attachments:
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    img_part: dict[str, Any] = {
                        "type": "image",
                        "image_url": item["url"],
                    }
                    mime = item.get("content_type")
                    if isinstance(mime, str) and mime.strip():
                        img_part["mime_type"] = mime.strip()
                    parts.append(img_part)
        return parts

    async def _emit_relay_lifecycle(
        self, message: InboundMessage, update: RelayLifecycleUpdate
    ) -> None:
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

    async def _ensure_binding(
        self, message: InboundMessage, *, agent_id: str, session_key: str
    ) -> SessionBinding:
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
        # Resolve per-agent config into session parameters.
        session_metadata = self._build_session_metadata(message, agent_id=agent_id)
        agent_skills = list(agent.skills) if agent.skills else None
        # refactor-406-M1 R6: per-agent enabled tools + PromptSlots + features (决策 1/6/8).
        # tool_allowlist is a TRUE whitelist (user may disable defaults); cron is a
        # gated capability appended when agent.cron_enabled.  PromptSlots carry all PA
        # conditional prompt content (heartbeat/cron → body, group context → tail),
        # built per-session from agent config + the group routing scenario in metadata.
        from personal_assistant.product import (  # noqa: PLC0415
            prompt_for,
            resolve_enabled_tools,
        )

        agent_tool_allowlist = resolve_enabled_tools(agent)
        session = await self._kernel.create_session(
            title=agent.title,
            workspace_root=agent.workspace_root,
            skills=agent_skills,
            enabled_tools=agent_tool_allowlist,
            features=dict(agent.features) if agent.features else None,
            prompt=prompt_for(agent, scenario=session_metadata),
            metadata=session_metadata,
        )
        kernel_session_id = session.session_id
        if not kernel_session_id:
            raise RuntimeError("kernel session creation did not return session_id")
        return self._session_store.bind(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=build_reply_context(message),
        )

    def _build_session_metadata(
        self, message: InboundMessage, *, agent_id: str
    ) -> dict[str, object] | None:
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
        # feat-379-M2 R6: inject per-agent feature flags and custom prompt supplement
        # into session metadata so the runtime can populate PromptContext.flags/vars.
        # agent.features may be empty dict (no overrides); always inject so runtime
        # can merge with FEATURE_REGISTRY default_on values.
        session_metadata["agent_features"] = dict(agent.features)
        if agent.custom_prompt:
            session_metadata["agent_custom_prompt"] = agent.custom_prompt
        # feat-394 M9 R4: standalone heartbeat_enabled/cron_enabled metadata keys removed.
        # Gate state lives in agent_features (injected above) and is read by
        # resolve_flags_from_metadata → ctx.flags in runtime.py.
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
                session_metadata["participant_agent_ids"] = (
                    _extract_participant_agent_ids(normalized_participants)
                )
            else:
                session_metadata["participant_agent_ids"] = [agent_id]
        else:
            session_metadata["conversation_type"] = "direct"
        return session_metadata

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
        policy = (
            (agent_config.group_reply_policy or "MENTION").upper()
            if agent_config
            else "MENTION"
        )
        if policy == "ALWAYS":
            return True
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
        # Provenance: openclaw/src/auto-reply/tokens.ts:3 HEARTBEAT_TOKEN = "HEARTBEAT_OK"
        # feat-394 decision 3: HEARTBEAT_OK is the heartbeat silence token (replaces NO_REPLY
        # in heartbeat turns); both are recognised here so the heartbeat delivery path and
        # the group-chat path share the same gate without special-casing the origin.
        stripped = text.strip()
        return stripped == "NO_REPLY" or stripped == "HEARTBEAT_OK"

    @classmethod
    def _should_suppress_no_reply(cls, reply_text: str, *, in_group: bool) -> bool:
        """Single guard deciding whether an agent text must be silently dropped.

        bugfix-416 #107: this is the ONE place that gates agent text on the
        NO_REPLY/HEARTBEAT_OK sentinel. **Any new agent-text delivery path MUST
        route its outgoing text through this guard before sending** — group chat
        has three independent delivery paths (main synchronous reply, streaming
        other-origin fan-out, background-task relay) and the original bug was
        precisely that the sentinel check lived only at the first one, so fan-out
        replies leaked the literal `NO_REPLY` into a bubble.

        ``in_group`` instead of an ``InboundMessage`` because the background relay
        path runs across a separate SSE loop and does not hold the originating
        message; agent-to-agent fan-out implies a group context, so those paths
        pass ``in_group=True``.
        """
        return in_group and cls._is_no_reply_token(reply_text)

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

        binding = await self._ensure_binding(
            message, agent_id=agent_id, session_key=session_key
        )

        if active_run_id is None:
            reply_text = "当前没有正在执行的操作。"
            outbound = await self._deliver_stop_ack(
                text=reply_text,
                binding=binding,
                agent_id=agent_id,
                ack_tag="stop-noop",
            )
            return PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id="",
                reply_text=reply_text,
                outbound=outbound,
            )

        agent_workspace_root_path = self._agents[agent_id].workspace_root
        # bugfix-417-M5 (#114): mark this run user-interrupted BEFORE interrupting so
        # the terminal reconcile attributes the in-flight tool card content to the
        # user. (active_run_id is the run /stop targets.)
        self._user_interrupted_runs.add(active_run_id)
        # interrupt() cancels the active run and any parked permission futures.
        self._kernel.interrupt(binding.kernel_session_id)
        # bugfix-417-fix2-r2 (#114): do NOT call _emit_terminal_reconcile here.
        # The reconcile is deferred to _await_terminal_run_async (which runs on the
        # original turn's stream consumer) so that message_id and running_tool_calls
        # are already set up by the observer's turn_start/tool_start handlers.
        # Calling reconcile directly here races the stream consumer and sees empty
        # state, causing the tool card CC content and bubble finalize to be dropped.
        # Log /stop command in session history without triggering a model run.
        # Use append_message (not submit) so the injected turn is persisted for the
        # next LLM call but does not itself spawn a new run (mirrors CC's
        # [Request interrupted by user for tool use] synthetic message; feat-332-M2).
        # bugfix-426 决策3 held-buffer: interrupt() above synchronously parks any
        # messages the user steered into the interrupted run into the session-level
        # held buffer; they ride the user's NEXT real submit (_run_turn /
        # _try_steer_active_run). Switching this /stop bookkeeping from submit to
        # append_message removes the synthetic run that bugfix-426 used flush_held=False
        # to shield — append_message never flushes held, so held still waits for the
        # next real message, exactly as 决策3 requires. No model/flush_held needed here.
        self._kernel.append_message(
            session_id=binding.kernel_session_id,
            role="user",
            content="[Request interrupted by user for tool use]",
            workspace_root=agent_workspace_root_path,
        )
        reply_text = "已停止当前操作。"
        outbound = await self._deliver_stop_ack(
            text=reply_text,
            binding=binding,
            agent_id=agent_id,
            ack_tag="stop-ack",
        )
        return PipelineResult(
            agent_id=agent_id,
            session_key=session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id=active_run_id,
            reply_text=reply_text,
            outbound=outbound,
        )

    async def _deliver_stop_ack(
        self,
        *,
        text: str,
        binding: Any,
        agent_id: str,
        ack_tag: str,
    ) -> OutboundMessage | None:
        """Deliver a /stop acknowledgement to the originating IM conversation.

        bugfix-417-fix2 (#114, Issue 2): the /stop ack is NOT a kernel turn, so it has
        no observer streaming path; the old ``outbound_router.send_text`` →
        ``WebRelayAdapter.send`` only appended to an in-memory list and never reached
        IM (so journey 13's "当前没有正在执行的操作。" + the "已停止当前操作。" reply
        were both silently dropped). Deliver via ``_bg_reply_sender`` — the same live
        ``send_agent_message`` WS path background-task replies use — so the ack appears
        as an agent message in the conversation. Falls back to the (no-op) router when
        the sender is not wired (e.g. unit tests / product-agnostic pipeline).

        bugfix-417-fix2-r2 (#114): ``from_session_id`` must be parseable by IM's
        ``_resolve_dispatch_source_from_session_id`` so that ``_handle_agent_message``
        can resolve the source agent user and return an ack. Using the raw
        ``kernel_session_id`` or an unrecognized suffix (e.g. ``|stop-ack``) leaves the
        ack unresolvable, the ack never returns, and the Gateway's single-frame-pending
        websocket queue stalls all subsequent streaming_delta frames.
        """
        if self._bg_reply_sender is not None:
            try:
                await self._bg_reply_sender(
                    text,
                    binding.reply_context,
                    # Stable idempotency key so repeated /stop acks are deduplicated
                    # by IM's agent_message_dispatch_log. Format mirrors BACKGROUND_TASK
                    # relay: agent_id|tool_call:<stable-key>.
                    f"{agent_id}|tool_call:{binding.kernel_session_id}:{ack_tag}",
                )
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning(
                    "stop ack delivery via bg_reply_sender failed: %s", exc
                )
            return None
        # No live sender (tests / agnostic pipeline): keep the recorded outbound so
        # existing assertions on outbound_router still observe the reply text.
        return self._outbound_router.send_text(
            text=text, reply_context=binding.reply_context
        )

    def register_agent(self, agent: AgentWorkspaceConfig) -> None:
        """Add or replace one live agent workspace binding for future sessions."""
        self._agents[agent.agent_id] = agent
        if self._default_agent_id is None:
            self._default_agent_id = agent.agent_id

    def _resolve_model(self, agent_id: str) -> str | None:
        """Resolve the model for one turn (bugfix-429 决策2).

        Reads ``agent.default_model`` fresh from the live ``self._agents`` map
        (config.sync updates it via register_agent) so a model change applies to
        the next turn, including existing/old sessions. The fallback rule lives in
        the shared ``resolve_run_model`` helper (fix-r1 #3).
        """
        return resolve_run_model(
            self._agents.get(agent_id),
            product_default=self._product_default_model,
        )

    def _binding_matches_workspace_root(
        self, session_id: str, *, expected_workspace_root: str
    ) -> bool:
        """Return whether one bound kernel session carries the expected workspace metadata.

        Notes:
            In the SDK (in-process) mode, sessions are always created with the correct
            workspace_root in the same process, so stale workspace mismatches cannot
            occur across process restarts (the in-memory session store is fresh each
            startup).  We still verify via get_session so legacy sessions persisted
            before M3 are refreshed on the first inbound message.

            Older test doubles may not implement get_session yet; in that case we
            preserve the historical reuse behavior.
        """

        get_session = getattr(self._kernel, "get_session", None)
        if not callable(get_session):
            return True
        try:
            session_payload = get_session(
                session_id=session_id, workspace_root=expected_workspace_root
            )
        except RuntimeError:
            return False
        # workspace_root is a top-level key in the session payload (set by
        # Kernel.get_session from Session.workspace_root).  Reading it from
        # metadata would require the gateway to inject a redundant copy on
        # create_session, creating two sources of truth — refactor-387 regression.
        workspace_root = session_payload.get("workspace_root")
        return (
            isinstance(workspace_root, str)
            and workspace_root.strip() == expected_workspace_root.strip()
        )

    def drop_agent_sessions(self, agent_id: str) -> None:
        """Drop existing kernel-session bindings for one agent after config sync."""
        self._session_store.drop_agent(agent_id)

    async def _ensure_background_subscriber(
        self,
        *,
        kernel_session_id: str,
        last_sequence: int,
        reply_context: ReplyContext | None = None,
        session_key: str | None = None,
    ) -> None:
        """Ensure one persistent background event subscriber is active for the session.

        Called after each main turn completes so that session-level events (e.g.
        self_evolution_review) published by background hooks after the main event
        loop terminates are still received and forwarded to ``_session_event_callback``.

        Also wires ``bg_run_output_callback`` so BACKGROUND_TASK-origin run output
        (assistant_message events from notification-triggered runs) is relayed back to
        the originating IM conversation. This closes the M3 gap: M1 fixed the kernel to
        inject and re-run BACKGROUND_TASK notifications; M3 fixes the gateway to relay the
        resulting assistant reply back to IM (bugfix-404-M3).

        If a subscriber is already active for this session (from a previous turn) it
        is left running — re-creation would lose events between turns.

        Args:
            kernel_session_id: Kernel session to subscribe to.
            last_sequence: Last event sequence number seen by the main turn's loop,
                used as ``after_sequence`` so the subscriber replays events missed
                between turn termination and subscription start.
            reply_context: Routing context for the originating IM conversation.
                When provided and ``_bg_reply_sender`` is wired, BACKGROUND_TASK run
                output is relayed to IM via the real IM send path.
            session_key: Gateway session key (``channel:conv_id:agent_id``).
                Used to extract the agent_id for the bg_reply_sender call.
        """
        # Require at least one of session_event_callback or reply_context to be set.
        # Without both, there is nothing to do with received events.
        if self._session_event_callback is None and reply_context is None:
            return
        if kernel_session_id in self._bg_subscribers:
            return

        on_session_event_cb = self._session_event_callback

        async def _on_session_event(event: Mapping[str, Any]) -> None:
            if on_session_event_cb is not None:
                await on_session_event_cb(kernel_session_id, event)

        # bugfix-404-M3: when reply_context is available and _bg_reply_sender is wired
        # (by main.py after im_connection_manager is created), relay BACKGROUND_TASK-origin
        # assistant_message events back to the originating IM conversation.
        # outbound_router.send_text() → WebRelayAdapter.sent.append() is a no-op for the
        # web_relay channel; _bg_reply_sender uses im_connection_manager.send_agent_message()
        # which is the real IM WebSocket send path.
        bg_run_output_callback = None
        if reply_context is not None and self._bg_reply_sender is not None:
            captured_reply_context = reply_context
            bg_reply_sender = self._bg_reply_sender
            # Extract agent_id from session_key ("channel:conv_id:agent_id").
            # Fall back to empty string if session_key is absent or malformed.
            agent_id_for_relay = session_key.rsplit(":", 1)[-1] if session_key else ""
            # bugfix-404 F1: build a stable per-event idempotency key so IM
            # deduplicates replayed BACKGROUND_TASK replies after gateway restarts.
            # IM dedup path: from_session_id contains "|tool_call:<key>" →
            # dispatch_request_key = f"{agent_id}:{key}" used as idempotency token
            # (see gateway_handler.py _handle_agent_message / _resolve_dispatch_source).
            # Key = kernel_session_id + ":" + event sequence number (stable, per-event).
            captured_kernel_session_id = kernel_session_id

            async def _relay_bg_run_output(event: Mapping[str, Any]) -> None:
                content = event.get("content")
                if isinstance(content, str) and content.strip():
                    text = content.strip()
                    # bugfix-416 #107: BACKGROUND_TASK relay is the third agent-text
                    # delivery path; route through the shared guard so a NO_REPLY
                    # sentinel never reaches IM. Background relays only run for group
                    # fan-out contexts, so in_group=True.
                    if self._should_suppress_no_reply(text, in_group=True):
                        return
                    seq = event.get("_id") or event.get("sequence_num")
                    idempotency_key = (
                        f"{captured_kernel_session_id}:{seq}"
                        if seq is not None
                        else captured_kernel_session_id
                    )
                    from_session_id = (
                        f"{agent_id_for_relay}|tool_call:{idempotency_key}"
                    )
                    await bg_reply_sender(
                        text,
                        captured_reply_context,
                        from_session_id,
                    )

            bg_run_output_callback = _relay_bg_run_output

        # In-process mode: the subscriber uses the Kernel directly via its stream() method.
        # BackgroundSessionEventSubscriber accepts any object with stream_session(); we
        # adapt the Kernel's stream() method into the expected call shape.
        subscriber = BackgroundSessionEventSubscriber(
            kernel_client=_KernelStreamAdapter(self._kernel, kernel_session_id),
            session_id=kernel_session_id,
            on_event=_on_session_event,
            after_sequence=last_sequence,
            bg_run_output_callback=bg_run_output_callback,
        )
        self._bg_subscribers[kernel_session_id] = subscriber
        await subscriber.start()

    def _require_known_agent(self, agent_id: str) -> str:
        if agent_id not in self._agents:
            raise LookupError(f"unknown agent_id: {agent_id}")
        return agent_id

    async def _await_terminal_run_async(
        self,
        *,
        kernel_session_id: str,
        run_id: str,
        anchor_sequence: int | None = None,
        on_other: Callable[[Mapping[str, object]], Awaitable[None] | None]
        | None = None,
    ) -> tuple[Mapping[str, object], str]:
        """Consume in-process event stream until terminal run_status for run_id.

        Non-target events are passed to ``on_other`` if provided.  This lets
        callers route background-task or heartbeat runs through the same
        session-key serial queue while the user run is in progress.

        anchor_sequence is passed to kernel.stream as after_sequence so any
        events published before this call are replayed from the event hub buffer.
        """
        reply_text = ""
        run_state: Mapping[str, object] | None = None

        stream = self._kernel.stream(
            kernel_session_id, after_sequence=anchor_sequence or 0
        )
        # bugfix-417-M3 R4: the idle watchdog is now a pure liveness detector. All three
        # alive-but-quiet windows (silent long tool / awaiting LLM / parked on a
        # permission decision) emit periodic ``run_heartbeat`` events on the same stream
        # (kernel decisions 2-4), so ANY event — business OR heartbeat — resets the idle
        # timer below. The previous ``awaiting_permission`` special-case branch is gone:
        # a parked permission wait now stays alive via its heartbeat, not a per-window
        # exemption, and a Gateway/kernel crash stops the heartbeat so a genuinely dead
        # run is still reaped after the timeout (decision 4 crash detection).
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        anext(stream),
                        timeout=self._run_idle_timeout_seconds,
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    self._kernel.cancel(run_id)
                    # bugfix-417-M3 R4 (decision 5): the watchdog reaped this run for
                    # losing liveness (no event/heartbeat in the window) — a STALL/中断,
                    # distinct from a tool hitting its own deadline (tool_timeout). Close
                    # any in-flight tool_call with reason="stalled" (badge=已中断).
                    self._emit_terminal_reconcile(run_id, reason="stalled")
                    raise TimeoutError(
                        "kernel run "
                        f"{run_id} produced no events for "
                        f"{self._run_idle_timeout_seconds:g}s"
                    ) from None

                # Kernel.stream() yields flattened dicts (sdk-fix-r3); .get() works directly.
                if event.get("run_id") != run_id:
                    if on_other is not None:
                        result = on_other(event)
                        if asyncio.iscoroutine(result):
                            await result
                    continue
                if self._kernel_event_observer is not None:
                    # Bridge consumer raises if it cannot translate — let it propagate so we don't
                    # silently swallow malformed kernel events.
                    result = self._kernel_event_observer(event)
                    if asyncio.iscoroutine(result):
                        await result
                event_name = event.get("event")
                # bugfix-417-M3 R4: no permission exemption to toggle — liveness is
                # carried by run_heartbeat on the stream, so reaching here (any event)
                # already reset the idle timer above.
                if event_name == "assistant_message":
                    content = event.get("content")
                    if isinstance(content, str):
                        reply_text = content
                elif event_name == "run_status":
                    status = event.get("status")
                    if status in _TERMINAL_RUN_STATUSES:
                        run_state = event
                        # bugfix-380: break instead of raising immediately so any
                        # assistant_message event already in the SSE buffer gets consumed
                        # before we exit. The raise happens below after the loop.
                        break
        finally:
            close_stream = getattr(stream, "aclose", None)
            if callable(close_stream):
                await close_stream()

        if run_state is None:
            # bugfix-410-M2 R3 (#97): stream ended without terminal status (e.g. the
            # run was cancelled out-of-band) — still close any in-flight tool_call.
            # bugfix-417-fix2-r2 (#114): if the stream was torn by a user /stop,
            # reconcile with user attribution and finalize the bubble cleanly.
            user_stopped = run_id in self._user_interrupted_runs
            self._emit_terminal_reconcile(run_id, reason="interrupted")
            if user_stopped:
                return ({"status": "cancelled"}, reply_text)
            raise RuntimeError("stream ended without terminal run_status")

        status = run_state.get("status")
        if status == "cancelled":
            # bugfix-417-fix2-r2 (#114): a cancelled terminal caused by user /stop is
            # an EXPECTED clean termination. Reconcile with user attribution and
            # finalize the bubble, then return cleanly so _run completes the turn.
            user_stopped = run_id in self._user_interrupted_runs
            self._emit_terminal_reconcile(run_id, reason="interrupted")
            if user_stopped:
                return run_state, reply_text
            # A non-user cancelled (watchdog idle reap / defensive cancel) is still
            # an error — Req B's "stalled/crashed run → failed" reaping does NOT regress.
            raise RuntimeError(
                self._extract_run_error(run_state, fallback_status=str(status or ""))
            )
        if status != "completed":
            # bugfix-410-M2 R3 (#97): any non-completed terminal closes in-flight
            # tool_calls (badge=已中断) via the reconcile.
            self._emit_terminal_reconcile(run_id, reason="interrupted")
            raise RuntimeError(
                self._extract_run_error(run_state, fallback_status=str(status or ""))
            )

        return run_state, reply_text

    def _emit_terminal_reconcile(self, run_id: str, *, reason: str) -> None:
        """Feed a synthetic run_terminal_reconcile event to the kernel event observer.

        bugfix-410-M2 R3 (#97): the observer tracks tool_calls that received
        tool_start but not tool_end. This synthetic event tells it to close those
        in-flight calls with a reason so the IM badge stops spinning. No-op when no
        observer is wired (product-agnostic pipeline default).

        bugfix-417-M5 (#114): when this run was stopped by an explicit user /stop,
        attach the CC-identical user-attribution content so the in-flight tool card
        shows the same body the model sees in the transcript. The badge reason stays
        "interrupted" (renders 「已中断」); only the displayed content is attributed
        to the user — system reaps (watchdog/crash) carry no content.
        """
        if self._kernel_event_observer is None:
            return
        content: str | None = None
        # bugfix-417-fix2-r2 (#114): membership in _user_interrupted_runs is the
        # "user /stop" signal. It is cleared once in the per-run finally chokepoint
        # (so the set stays bounded), but _emit_terminal_reconcile may be called
        # from _await_terminal_run_async which runs BEFORE that finally, so the
        # marker is still present when reconcile fires.
        user_stopped = run_id in self._user_interrupted_runs
        if user_stopped:
            content = USER_INTERRUPT_RECOVERY_CONTENT
        event: dict[str, object] = {
            "event": "run_terminal_reconcile",
            "run_id": run_id,
            "reason": reason,
        }
        if content is not None:
            event["content"] = content
        if user_stopped:
            # bugfix-417-fix2 (#114, Issue 1): only a user /stop finalizes the agent
            # bubble here (the kernel emits no turn_end on cancel). A watchdog/crash
            # reap must NOT set this — its bubble stays failed via the phase=failed
            # lifecycle (Req B no-regression).
            event["finalize_bubble"] = True
        result = self._kernel_event_observer(event)
        # The reconcile branch schedules its sends via loop.create_task and returns
        # None; guard anyway in case a future observer returns a coroutine.
        if asyncio.iscoroutine(result):  # pragma: no cover - defensive
            asyncio.ensure_future(result)

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
        if event_name == "run_heartbeat":
            # bugfix-417-M3 R4: liveness heartbeat (tool / LLM-await / parked-permission)
            # maps to a Run Activity liveness signal so consumers that track run activity
            # see the run is alive during an otherwise silent window.
            return "agent.run.heartbeat"
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
    def _extract_run_error(
        run_state: Mapping[str, object], *, fallback_status: str
    ) -> str:
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
    def _extract_reply_text(
        cls, run_state: Mapping[str, object], *, streamed_text: str = ""
    ) -> str:
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
            agent_id = _optional_stripped_text(
                item.get("agent_id")
            ) or _optional_stripped_text(item.get("id"))
            if agent_id is None:
                continue
            entry: dict[str, str] = {"type": "agent", "agent_id": agent_id}
        else:
            user_id = _optional_stripped_text(
                item.get("user_id")
            ) or _optional_stripped_text(item.get("id"))
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


class _KernelStreamAdapter:
    """Adapt Kernel.stream() to the stream_session(session_id, ...) interface.

    BackgroundSessionEventSubscriber calls stream_session(session_id, last_event_id,
    workspace_root) on its kernel_client.  In SDK mode, the session is already bound
    to a fixed session_id; this adapter forwards calls to Kernel.stream() ignoring
    the workspace_root parameter (not needed in-process).

    Kernel.stream() now produces flattened dicts (refactor-387 sdk-fix-r3), so no
    normalization is needed here — events are forwarded directly.
    """

    def __init__(self, kernel: "Kernel", session_id: str) -> None:
        self._kernel = kernel
        self._session_id = session_id

    async def stream_session(
        self,
        *,
        session_id: str,
        last_event_id: int | None = None,
        workspace_root: str | None = None,
        **_kwargs: object,
    ):
        # last_event_id maps to after_sequence; workspace_root is ignored in-process.
        # Kernel.stream() yields flattened dicts — forward directly.
        async for event in self._kernel.stream(
            session_id or self._session_id,
            after_sequence=last_event_id or 0,
        ):
            yield event
