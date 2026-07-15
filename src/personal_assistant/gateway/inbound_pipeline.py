"""Inbound four-step decision pipeline for Node Gateway channel messages."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from typing import Protocol

from personal_assistant.channels.base import (
    InboundMessage,
    OutboundMessage,
    ReplyContext,
)
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    resolve_run_model,
)
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog, LiveAgentSnapshot
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway import inbound_models as _inbound_models
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import (
    GatewayShutdownBeforeSubmit,
    SessionRunQueue,
    SessionRunQueueSealed,
)
from personal_assistant.gateway.runtime_protocol import external_identity_from_message
from personal_assistant.gateway.reply_visibility import (
    ReplyVisibilityPolicy,
    is_protocol_silence_token,
    should_suppress_reply,
)
from personal_assistant.gateway.session_keys import (
    SessionBinding,
    SessionBindingStore,
    build_external_session_key,
    build_reply_context,
    build_session_key,
    session_binding_store,
)
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)

from agent.sdk import TERMINAL_RUN_STATUSES, USER_INTERRUPT_RECOVERY_CONTENT

if TYPE_CHECKING:
    from agent.sdk.kernel import Kernel


class ShadowConversationSync(Protocol):
    """Best-effort IM shadow conversation writer for external-channel inbound."""

    async def sync_user_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> str | None:
        """Persist one inbound user message and return the IM shadow conversation id."""


_TERMINAL_RUN_STATUSES = TERMINAL_RUN_STATUSES
# Default port for the Gateway's internal HTTP dispatch endpoint.
_DEFAULT_GATEWAY_INTERNAL_PORT = 8089
# Keep the Gateway's run owner aligned with IM's relay watchdog. The timeout is
# idle-based: every kernel event resets it, so active long-running tool loops continue.
_DEFAULT_RUN_IDLE_TIMEOUT_SECONDS = 120.0
_MAX_SESSION_DRAIN_LOCKS = 4096

# bugfix-433 决策5: fixed user-facing messages for image failure types. Worker MUST
# NOT paraphrase — these are part of the contract (incident Q6 / design 决策5 表).
_IMAGE_FAILURE_MESSAGES: dict[str, str] = {
    "download": "这张图片没能加载，我没有收到它，无法据此回复。请重新发送图片试试。",
    "oversize": (
        "这张图片太大了，超出可接收的大小，我没能收到它，"
        "无法据此回复。请压缩或换一张更小的图片后重新发送。"
    ),
    "corrupt": "这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。",
}


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
        image_resolver: Image policy owner used to resolve inbound attachment metadata.
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
        agents: tuple[AgentWorkspaceConfig, ...] = (),
        outbound_router: OutboundRouter,
        run_queue: SessionRunQueue,
        session_store: SessionBindingStore = session_binding_store,
        agent_catalog: LiveAgentCatalog | None = None,
        session_binder: GatewaySessionBinder | None = None,
        channel_bindings: Mapping[str, str] | None = None,
        default_agent_id: str | None = None,
        relay_lifecycle_callback: _inbound_models.RelayLifecycleCallback | None = None,
        group_context_store: GroupContextStore | None = None,
        gateway_internal_port: int = _DEFAULT_GATEWAY_INTERNAL_PORT,
        run_idle_timeout_seconds: float = _DEFAULT_RUN_IDLE_TIMEOUT_SECONDS,
        kernel_event_observer: Callable[[Mapping[str, Any]], None] | None = None,
        product_default_model: str | None = None,
        image_resolver: ImageAttachmentResolver | None = None,
        background_subscriptions: BackgroundSubscriptionManager | None = None,
        shadow_sync: ShadowConversationSync | None = None,
        bg_reply_sender: Callable[[str, ReplyContext, str], Awaitable[None]]
        | None = None,
        max_session_drain_locks: int = _MAX_SESSION_DRAIN_LOCKS,
    ) -> None:
        if run_idle_timeout_seconds <= 0:
            raise ValueError("run_idle_timeout_seconds must be > 0")
        self._kernel = kernel
        catalog = agent_catalog or LiveAgentCatalog(agents)
        binder = session_binder or GatewaySessionBinder(
            catalog=catalog,
            repository=session_store,
            kernel=kernel,
        )
        self._agent_catalog = catalog
        self._session_binder = binder
        # bugfix-429 决策2: the product owns the default model. Each turn submits
        # The operation snapshot supplies agent.default_model, and this product
        # default applies when the Agent has not selected one.
        self._product_default_model = product_default_model
        self._image_resolver = image_resolver or ImageAttachmentResolver()
        self._shadow_sync = shadow_sync
        self._outbound_router = outbound_router
        self._run_queue = run_queue
        self._channel_bindings = dict(channel_bindings or {})
        snapshots = catalog.values_snapshot()
        self._default_agent_id = default_agent_id or (
            snapshots[0].agent_id if snapshots else None
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
        self._session_drain_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._max_session_drain_locks = max(1, max_session_drain_locks)
        # bugfix-417-M5 (#114): run_ids stopped by an explicit user /stop, so the
        # terminal reconcile can attribute the in-flight tool card's content to the
        # user ("[Request interrupted by user for tool use]") instead of the generic
        # system-interrupt body. Bounded: entries are discarded on reconcile.
        self._user_interrupted_runs: set[str] = set()
        # feat-340-M2: bootstrap wires this to an IM event_bridge consumer so the browser
        # sees live tool_call / token_usage events; default None keeps pipeline product-agnostic.
        self._kernel_event_observer = kernel_event_observer
        # bugfix-404-M3: async callable (text, reply_context, agent_id) → None that sends
        # a BACKGROUND_TASK run reply back to IM.  Wired by main.py after im_connection_manager
        # is created.  None disables BACKGROUND_TASK relay (outbound_router.send_text() is a
        # no-op for the web_relay channel, so this must be the real IM send path).
        self._bg_reply_sender = bg_reply_sender
        self._background_subscriptions = background_subscriptions

    @property
    def agent_catalog(self) -> LiveAgentCatalog:
        """Return the shared live Agent snapshot owner."""

        return self._agent_catalog

    @property
    def session_binder(self) -> GatewaySessionBinder:
        """Return the shared Gateway session binding owner."""

        return self._session_binder

    def seal(self) -> None:
        """Synchronously reject new queued runs and background subscriptions."""

        self._run_queue.seal_and_cancel_pending()
        if self._background_subscriptions is not None:
            self._background_subscriptions.seal()

    async def settle_admission(self, deadline: float) -> None:
        """Wait for accepted turns to cross submit-or-rollback by one deadline."""

        await self._run_queue.settle_admission(deadline)

    def set_shadow_sync(self, shadow_sync: ShadowConversationSync | None) -> None:
        """Replace the external shadow adapter used by subsequent inbound messages."""

        self._shadow_sync = shadow_sync

    async def handle_inbound(self, message: InboundMessage) -> _inbound_models.PipelineResult | None:
        """Process one inbound message through route, session, queue, and reply steps.

        Returns:
            The observable pipeline result when the message is allowed to run, or
            ``None`` when group-chat mention gating suppresses execution.
        """

        agent_id = self._resolve_agent(message)
        agent = self._agent_catalog.require(agent_id)
        agent_config = agent.config
        should_process = self._should_process(
            message, agent_id=agent_id, agent_config=agent_config
        )

        # M247: prefer sender_display_name from relay metadata over raw external_user_id (UUID).
        # Relay metadata supplies display_name when the IM service could resolve it.
        # Fallback to external_user_id ensures pre-M247 payloads still get the UUID prefix.
        sender_label = _resolve_sender_label(message)
        sync_only = message.metadata.get("sync_only") is True
        message = await self._sync_external_shadow_message(message, agent_id=agent_id)

        if message.is_group and self._group_context_store is not None:
            if sync_only or not should_process:
                # This relay's agent is not addressed — buffer message as background context
                # for this agent's own future turn.  Each agent receives its own relay from IM,
                # so we only write to this agent's buffer key (no cross-agent fan-out).
                # Store sender label (display_name or UUID) for [sender] text prefixes.
                self._group_context_store.append(
                    self._group_buf_key_for_agent(message, agent_id),
                    message.text,
                    sender=sender_label,
                )

        if sync_only:
            return None
        if not should_process:
            return None
        session_key = build_session_key(message, agent_id=agent_id)

        if self._is_stop_command(message, agent_id=agent_id):
            return await self._handle_stop_command(
                message, agent=agent, session_key=session_key
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
                    agent=agent,
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
            return await self._submit_queued_turn(
                message,
                agent=agent,
                session_key=session_key,
                sender_label=sender_label,
                prebuilt_parts=fallback_parts,
            )

        return await self._submit_queued_turn(
            message,
            agent=agent,
            session_key=session_key,
            sender_label=sender_label,
        )

    async def _submit_queued_turn(
        self,
        message: InboundMessage,
        *,
        agent: LiveAgentSnapshot,
        session_key: str,
        sender_label: str,
        prebuilt_parts: list[dict[str, Any]] | None = None,
    ) -> _inbound_models.PipelineResult:
        admission_event = asyncio.Event()

        async def _on_cancel(error: GatewayShutdownBeforeSubmit) -> None:
            await self._emit_relay_lifecycle(
                message,
                _inbound_models.RelayLifecycleUpdate(
                    phase="failed",
                    agent_id=agent.agent_id,
                    session_key=session_key,
                    error=error.reason,
                ),
            )

        try:
            return await self._run_queue.submit(
                session_key,
                lambda: self._run_turn(
                    message,
                    agent=agent,
                    session_key=session_key,
                    sender_label=sender_label,
                    prebuilt_parts=prebuilt_parts,
                    admission_event=admission_event,
                ),
                on_cancel=_on_cancel,
                admission_event=admission_event,
            )
        except SessionRunQueueSealed:
            await self._emit_relay_lifecycle(
                message,
                _inbound_models.RelayLifecycleUpdate(
                    phase="failed",
                    agent_id=agent.agent_id,
                    session_key=session_key,
                    error=GatewayShutdownBeforeSubmit.reason,
                ),
            )
            raise

    async def _try_steer_active_run(
        self,
        message: InboundMessage,
        *,
        agent: LiveAgentSnapshot,
        session_key: str,
        sender_label: str,
    ) -> tuple[_inbound_models.PipelineResult | None, list[dict[str, Any]]] | None:
        """Attempt to inject this message into the session's active run.

        Returns:
            None when there is no bound/active run to steer (caller falls through
            to a normal queued run). Otherwise a ``(injected_result, parts)`` pair:
            ``injected_result`` is the _inbound_models.PipelineResult when the kernel injected into
            the active run (caller returns it directly, no queued run); it is None
            when the active run ended in the race window, in which case ``parts``
            (already built, buffer drained) must be submitted by the caller's
            queued run instead of re-draining.
        """
        agent_id = agent.agent_id
        binding = await self._ensure_binding(
            message, agent=agent, session_key=session_key
        )
        parts, failure_kind = await self._build_message_parts(
            message, agent_id=agent_id, sender_label=sender_label
        )
        if failure_kind is not None:
            return (
                await self._reply_image_failure(
                    failure_kind,
                    message=message,
                    agent_id=agent_id,
                    session_key=session_key,
                    binding=binding,
                ),
                [],
            )
        agent_workspace_root_path = agent.config.workspace_root
        run_record = self._kernel.submit(
            session_id=binding.kernel_session_id,
            parts=parts,
            workspace_root=agent_workspace_root_path,
            steer=True,
            model=self._resolve_model(agent),
        )
        if not getattr(run_record, "injected", False):
            # Race: run ended before the enqueue. Caller re-runs with these parts.
            return None, parts
        await self._emit_relay_lifecycle(
            message,
            _inbound_models.RelayLifecycleUpdate(
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
            _inbound_models.PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id=run_record.run_id,
                reply_text="",
                outbound=None,
            ),
            parts,
        )

    async def _sync_external_shadow_message(
        self, message: InboundMessage, *, agent_id: str
    ) -> InboundMessage:
        sync = self._shadow_sync
        if sync is None or not _is_external_channel_inbound(message):
            return message
        metadata = dict(message.metadata)
        try:
            shadow_conversation_id = await sync.sync_user_message(
                message, agent_id=agent_id
            )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "external shadow sync failed channel=%s chat=%s agent=%s: %s",
                message.channel_name,
                message.external_chat_id,
                agent_id,
                exc,
            )
            shadow_conversation_id = None
        if isinstance(shadow_conversation_id, str) and shadow_conversation_id.strip():
            metadata["shadow_conversation_id"] = shadow_conversation_id.strip()
        else:
            metadata.pop("shadow_conversation_id", None)
        return replace(message, metadata=metadata)

    async def _run_turn(
        self,
        message: InboundMessage,
        *,
        agent: LiveAgentSnapshot,
        session_key: str,
        sender_label: str,
        prebuilt_parts: list[dict[str, Any]] | None = None,
        admission_event: asyncio.Event,
    ) -> _inbound_models.PipelineResult:
        agent_id = agent.agent_id
        run_id: str | None = None
        try:
            binding = await self._ensure_binding(
                message, agent=agent, session_key=session_key
            )
            # Build parts once (drains the group buffer). The steer race path
            # passes already-built parts so the buffer is not drained twice.
            # bugfix-426-M3: hold the per-session drain lock around the drain so a
            # concurrent steer fast-path cannot interleave its own drain with this
            # one (the run_queue only serializes normal-vs-normal, not steer-vs-
            # normal). prebuilt_parts means the steer path already drained under the
            # lock, so we skip both the drain and the lock.
            failure_kind: str | None = None
            if prebuilt_parts is not None:
                parts = prebuilt_parts
            else:
                async with self._drain_lock_for(session_key):
                    parts, failure_kind = await self._build_message_parts(
                        message, agent_id=agent_id, sender_label=sender_label
                    )
                if failure_kind is not None:
                    result = await self._reply_image_failure(
                        failure_kind,
                        message=message,
                        agent_id=agent_id,
                        session_key=session_key,
                        binding=binding,
                    )
                    admission_event.set()
                    return result
            agent_workspace_root_path = agent.config.workspace_root
            # submit() is sync, non-blocking — schedules the turn on RunsRegistry's
            # background loop and returns immediately with a RunRecord.
            run_record = self._kernel.submit(
                session_id=binding.kernel_session_id,
                parts=parts,
                workspace_root=agent_workspace_root_path,
                model=self._resolve_model(agent),
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
            admission_event.set()
            await self._emit_relay_lifecycle(
                message,
                _inbound_models.RelayLifecycleUpdate(
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
            if self._background_subscriptions is not None:
                await self._background_subscriptions.ensure(
                    BackgroundSubscriptionRequest(
                        session_id=binding.kernel_session_id,
                        after_sequence=anchor_sequence or 0,
                        reply_context=binding.reply_context,
                        agent_id=agent_id,
                    )
                )
            await self._emit_relay_lifecycle(
                message,
                _inbound_models.RelayLifecycleUpdate(
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
            ) and not (
                _is_external_channel_inbound(message)
                and self._is_no_reply_token(reply_text)
            ):
                reply_context = binding.reply_context
                if _is_external_channel_inbound(message):
                    reply_context = replace(
                        reply_context,
                        metadata={
                            **dict(reply_context.metadata),
                            "reply_phase": "final",
                            "reply_dedupe_key": (f"{run_id}:text:{reply_text.strip()}"),
                            **(
                                {
                                    "feishu_message_id": str(
                                        message.metadata["feishu_message_id"]
                                    )
                                }
                                if isinstance(
                                    message.metadata.get("feishu_message_id"), str
                                )
                                and str(message.metadata["feishu_message_id"]).strip()
                                else {}
                            ),
                        },
                    )
                outbound = self._outbound_router.send_text(
                    text=reply_text, reply_context=reply_context
                )
            else:
                lifecycle_detail = {"suppressed_by": "no_reply_token"}
            result = _inbound_models.PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id=run_id,
                reply_text=reply_text,
                outbound=outbound,
            )
            await self._emit_relay_lifecycle(
                message,
                _inbound_models.RelayLifecycleUpdate(
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
            try:
                await self._emit_relay_lifecycle(
                    message,
                    _inbound_models.RelayLifecycleUpdate(
                        phase="failed",
                        agent_id=agent_id,
                        session_key=session_key,
                        run_id=run_id,
                        error=str(exc),
                    ),
                )
            finally:
                admission_event.set()
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
        external_identity = external_identity_from_message(message)
        if external_identity is not None:
            return build_external_session_key(
                external_source=external_identity.external_source,
                external_chat_id=external_identity.external_chat_id,
                agent_id=agent_id,
            )
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
            self._trim_session_drain_locks()
        else:
            self._session_drain_locks.move_to_end(session_key)
        return lock

    def _trim_session_drain_locks(self) -> None:
        """Bound idle drain locks without evicting a lock that is in use."""
        checked_locked = 0
        while len(self._session_drain_locks) > self._max_session_drain_locks:
            session_key, lock = next(iter(self._session_drain_locks.items()))
            if lock.locked():
                self._session_drain_locks.move_to_end(session_key)
                checked_locked += 1
                if checked_locked >= len(self._session_drain_locks):
                    break
                continue
            self._session_drain_locks.popitem(last=False)
            checked_locked = 0

    async def _build_message_parts(
        self, message: InboundMessage, *, agent_id: str, sender_label: str
    ) -> tuple[list[dict[str, Any]], str | None]:
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

        Returns:
            ``(parts, None)`` when the kernel can be called. If an image attachment
            fails to download, exceeds the size cap, or is not a recognized image,
            returns ``([], failure_kind)`` and the caller stops the turn before
            ``kernel.submit``.
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
        # bugfix-433 决策1/5: resolve image attachments to self-contained base64
        # data URLs here at the inbound boundary. On any failure (download / size
        # / parse) the turn STOPS — the model is never called and a fixed message
        # is delivered to the user instead (决策5, outbound-only, not persisted).
        image_resolution = await self._image_resolver.resolve(attachments)
        if image_resolution.failure is not None:
            return [], image_resolution.failure
        parts.extend(image_resolution.parts)
        return parts, None

    async def _emit_relay_lifecycle(
        self, message: InboundMessage, update: _inbound_models.RelayLifecycleUpdate
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
                    if (
                        isinstance(candidate, str)
                        and self._agent_catalog.get(candidate) is not None
                    ):
                        return self._require_known_agent(candidate)
            reply_to_agent_id = metadata.get("reply_to_agent_id")
            if (
                isinstance(reply_to_agent_id, str)
                and self._agent_catalog.get(reply_to_agent_id) is not None
            ):
                return self._require_known_agent(reply_to_agent_id)
        if message.agent_id:
            return self._require_known_agent(message.agent_id)
        binding_key = f"{message.channel_name}:{message.external_chat_id}"
        bound_agent = self._channel_bindings.get(binding_key)
        if bound_agent is not None:
            return self._require_known_agent(bound_agent)
        if self._default_agent_id is None:
            snapshots = self._agent_catalog.values_snapshot()
            if not snapshots:
                raise LookupError("no default agent configured")
            return snapshots[0].agent_id
        return self._require_known_agent(self._default_agent_id)

    async def _ensure_binding(
        self,
        message: InboundMessage,
        *,
        agent: LiveAgentSnapshot,
        session_key: str,
    ) -> SessionBinding:
        return await self._session_binder.resolve(
            SessionBindingRequest(
                session_key=session_key,
                reply_context=build_reply_context(message),
                message=message,
                gateway_internal_port=self._gateway_internal_port,
            ),
            agent,
        )

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
        # feat-430 决策4: bare `/stop` is a control command — it must reach a running
        # agent regardless of the group @-mention policy (canonical gateway spec lists
        # 控制命令 as a group trigger). MENTION gating would otherwise drop a bare
        # `/stop`; let it through here. Idempotency for non-running agents is handled
        # downstream (kernel.interrupt is a no-op; the no-op ack is suppressed in group).
        if message.text.strip() == "/stop":
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
        return is_protocol_silence_token(text)

    @staticmethod
    def _should_suppress_no_reply(reply_text: str, *, in_group: bool) -> bool:
        """Apply the shared reply-visibility policy to a pipeline send.

        Canonical protocol-token classification lives in ``reply_visibility``.
        Runtime streaming and the pipeline's final/background delivery paths use
        that same policy so their user-visible behavior cannot drift.

        ``in_group`` instead of an ``InboundMessage`` because the background relay
        path runs across a separate SSE loop and does not hold the originating
        message; agent-to-agent fan-out implies a group context, so those paths
        pass ``in_group=True``.
        """
        policy = (
            ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
            if in_group
            else ReplyVisibilityPolicy.LITERAL_TEXT
        )
        return should_suppress_reply(reply_text, policy=policy)

    def _is_stop_command(self, message: InboundMessage, *, agent_id: str) -> bool:
        """Check whether the inbound message is a /stop control command.

        Supports ``/stop``, ``@agent /stop``, and ``/stop @agent`` forms.
        """
        text = message.text.strip()
        if text == "/stop":
            return True

        metadata = dict(message.metadata)
        mentioned_agent_ids = metadata.get("mentioned_agent_ids")
        structurally_mentioned = (
            isinstance(mentioned_agent_ids, list) and agent_id in mentioned_agent_ids
        )
        reply_to_agent_id = metadata.get("reply_to_agent_id")
        structurally_mentioned = structurally_mentioned or (
            isinstance(reply_to_agent_id, str) and reply_to_agent_id.strip() == agent_id
        )
        if not structurally_mentioned:
            mention = f"@{agent_id}"
            return text.replace(mention, "").strip() == "/stop"

        candidates = {f"@{agent_id}"}
        mentions = metadata.get("feishu_mentions")
        if isinstance(mentions, list):
            for mention in mentions:
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

    async def _handle_stop_command(
        self,
        message: InboundMessage,
        *,
        agent: LiveAgentSnapshot,
        session_key: str,
    ) -> _inbound_models.PipelineResult:
        """Handle /stop: interrupt active run or return friendly no-op message."""
        agent_id = agent.agent_id
        active_run_id: str | None = None
        async with self._active_runs_lock:
            active_run_id = self._active_runs.get(session_key)

        # feat-430 决策4 + fix-r2 (code-review P1.5): in a group every member agent receives
        # the broadcast `/stop`; a non-running member must produce ZERO side effects — no
        # ack bubble AND no kernel session. Short-circuit BEFORE _ensure_binding, which would
        # otherwise allocate an empty session for each idle group agent. Direct chats keep the
        # friendly ack (and binding) so an explicit /stop still gives the user feedback.
        if active_run_id is None and message.is_group:
            return _inbound_models.PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id="",
                run_id="",
                reply_text="",
                outbound=None,
            )

        binding = await self._ensure_binding(
            message, agent=agent, session_key=session_key
        )

        if active_run_id is None:
            reply_text = "当前没有正在执行的操作。"
            outbound = await self._deliver_stop_ack(
                text=reply_text,
                binding=binding,
                agent_id=agent_id,
                ack_tag="stop-noop",
                source_message=message,
            )
            return _inbound_models.PipelineResult(
                agent_id=agent_id,
                session_key=session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id="",
                reply_text=reply_text,
                outbound=outbound,
            )

        agent_workspace_root_path = agent.config.workspace_root
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
            source_message=message,
        )
        return _inbound_models.PipelineResult(
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
        source_message: InboundMessage | None = None,
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

        feat-447 Round 7: IM deduplicates agent messages by ``from_session_id``.
        A session-level key such as ``...:stop-noop`` would hide every later /stop
        acknowledgement in the same Feishu shadow conversation. Include the source
        inbound event id when present so distinct user-visible control events each
        render once, while platform retries of the same event remain idempotent.
        """
        from_session_id = _control_ack_from_session_id(
            agent_id=agent_id,
            kernel_session_id=binding.kernel_session_id,
            ack_tag=ack_tag,
            source_message=source_message,
        )
        if self._bg_reply_sender is not None:
            try:
                await self._bg_reply_sender(
                    text,
                    binding.reply_context,
                    from_session_id,
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

    async def _reply_image_failure(
        self,
        failure_kind: str,
        *,
        message: InboundMessage,
        agent_id: str,
        session_key: str,
        binding: SessionBinding,
    ) -> _inbound_models.PipelineResult:
        """Stop the turn and deliver the fixed image-failure message (决策5).

        The message is delivered via the same outbound sender as the /stop ack and is
        NOT written to kernel history — the turn was never submitted, so the next turn's
        context stays clean (no failure image, no failure text) with no replay filtering.
        """
        reply_text = _IMAGE_FAILURE_MESSAGES[failure_kind]
        outbound = await self._deliver_stop_ack(
            text=reply_text,
            binding=binding,
            agent_id=agent_id,
            ack_tag=f"image-error-{failure_kind}",
            source_message=message,
        )
        await self._emit_relay_lifecycle(
            message,
            _inbound_models.RelayLifecycleUpdate(
                phase="completed",
                agent_id=agent_id,
                session_key=session_key,
                run_id=None,
                reply_text=reply_text,
                detail={"image_failure": failure_kind},
            ),
        )
        return _inbound_models.PipelineResult(
            agent_id=agent_id,
            session_key=session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

    def _resolve_model(self, agent: LiveAgentSnapshot) -> str | None:
        """Resolve the model for one turn (bugfix-429 决策2).

        The caller supplies the operation's captured snapshot so every decision in
        the turn observes one complete Agent revision.
        """
        return resolve_run_model(
            agent.config,
            product_default=self._product_default_model,
        )


    def _require_known_agent(self, agent_id: str) -> str:
        if self._agent_catalog.get(agent_id) is None:
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
        # bugfix-465: a parked permission_request is intentionally waiting for a human
        # decision, not a sign of internal deadlock. While the run is in that window the
        # idle watchdog is fully suspended (timeout=None). The normal idle timeout is
        # restored the moment the kernel emits permission_resolved, so a genuine stall
        # after the decision is still reaped. Non-permission stalls keep the standard
        # idle timer on every stream read, preserving bugfix-417 crash detection.
        current_timeout = self._run_idle_timeout_seconds
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        anext(stream),
                        timeout=current_timeout,
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
                if event_name == "permission_request":
                    # bugfix-465: suspend the idle watchdog while the run is parked on a
                    # human decision. The user may leave, close the page, and come back;
                    # the run must stay alive until permission_resolved.
                    current_timeout = None
                elif event_name == "permission_resolved":
                    # bugfix-465: decision made; restore normal liveness detection so a
                    # subsequent crash or dead loop is still caught.
                    current_timeout = self._run_idle_timeout_seconds
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


def _control_ack_from_session_id(
    *,
    agent_id: str,
    kernel_session_id: str,
    ack_tag: str,
    source_message: "InboundMessage" | None,
) -> str:
    """Build an IM dispatch key for one user-visible control acknowledgement."""

    base = f"{agent_id}|tool_call:{kernel_session_id}:{ack_tag}"
    source_id = _control_ack_source_id(source_message)
    if source_id is None:
        return base
    return f"{base}:{source_id}"


def _control_ack_source_id(message: "InboundMessage" | None) -> str | None:
    if message is None:
        return None
    metadata = dict(message.metadata)
    for key in ("feishu_message_id", "relay_task_id", "idempotency_key", "message_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_dispatch_id_part(value)
    return None


def _normalize_dispatch_id_part(value: str) -> str:
    """Keep dispatch ids parseable while preserving enough platform identity."""

    normalized = "_".join(value.strip().split())
    normalized = normalized.replace("|", "_")
    return normalized[:160] if len(normalized) > 160 else normalized


def _is_external_channel_inbound(message: "InboundMessage") -> bool:
    """Return whether this message originated from an external channel, not IM relay."""
    external_identity = external_identity_from_message(message)
    return bool(
        external_identity is not None and external_identity.trigger_source != "im"
    )


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
