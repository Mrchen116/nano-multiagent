"""Own Gateway per-session run admission, interruption, and terminal cleanup."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
import logging
from typing import TYPE_CHECKING, Any

from agent.sdk import TERMINAL_RUN_STATUSES, USER_INTERRUPT_RECOVERY_CONTENT

from personal_assistant.channels.base import (
    InboundMessage,
    OutboundMessage,
    ReplyContext,
)
from personal_assistant.config.local_store import resolve_run_model
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)
from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.inbound_models import (
    InboundRunRequest,
    PipelineResult,
    RelayLifecycleCallback,
    RelayLifecycleUpdate,
    StopRunRequest,
    build_group_context_key,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.reply_visibility import (
    ReplyVisibilityPolicy,
    is_protocol_silence_token,
    should_suppress_reply,
)
from personal_assistant.gateway.run_queue import (
    GatewayShutdownBeforeSubmit,
    SessionRunQueue,
    SessionRunQueueSealed,
)
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import (
    SessionBinding,
    build_reply_context,
)

if TYPE_CHECKING:
    from agent.sdk.kernel import Kernel


_DEFAULT_GATEWAY_INTERNAL_PORT = 8089
_DEFAULT_RUN_IDLE_TIMEOUT_SECONDS = 120.0
_MAX_SESSION_TRANSITION_LOCKS = 4096
_SHUTDOWN_ACTIVE_RUN_CANCELLED = "gateway_shutdown_active_run_cancelled"
_IMAGE_FAILURE_MESSAGES: dict[str, str] = {
    "download": "这张图片没能加载，我没有收到它，无法据此回复。请重新发送图片试试。",
    "oversize": (
        "这张图片太大了，超出可接收的大小，我没能收到它，"
        "无法据此回复。请压缩或换一张更小的图片后重新发送。"
    ),
    "corrupt": "这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。",
}


@dataclass(frozen=True, slots=True)
class _ActiveRunHandle:
    """Freeze the Kernel session and Agent revision admitted for one active run."""

    run_id: str
    binding: SessionBinding
    agent: LiveAgentSnapshot


class SessionRunCoordinator:
    """Coordinate one Gateway session from admission through terminal cleanup.

    Args:
        kernel: In-process Kernel SDK instance.
        session_binder: Gateway session-binding owner used by every run/control path.
        outbound_router: Router that returns visible text to the originating channel.
        run_queue: Optional M2 queue implementation injected for focused tests. The
            coordinator is its sole runtime owner and never exposes it.
        group_context_store: Optional persistent ignored-group-chatter owner.
        image_resolver: Image policy used exactly once per admitted message.
        background_subscriptions: Optional persistent session-event subscription owner.
        gateway_internal_port: Internal dispatch port written into new session metadata.
        gateway_dispatch_url_provider: Current URL from the listener lifecycle owner.
        product_default_model: Product fallback when an Agent snapshot has no model.
        relay_lifecycle_callback: Optional relay accepted/running/terminal callback.
        kernel_event_observer: Optional runtime-delivery event translator.
        bg_reply_sender: Optional live IM/background text sender.
        run_idle_timeout_seconds: Maximum silence between Kernel liveness events.
        max_transition_locks: Maximum retained idle per-session admission locks.

    Notes:
        The per-session transition lock spans active inspection, destructive input
        preparation, Kernel steer admission, and normal submit plus active-marker
        publication. No await occurs between a successful normal submit and marker.
    """

    def __init__(
        self,
        *,
        kernel: "Kernel",
        session_binder: GatewaySessionBinder,
        outbound_router: OutboundRouter,
        run_queue: SessionRunQueue | None = None,
        group_context_store: GroupContextStore | None = None,
        image_resolver: ImageAttachmentResolver | None = None,
        background_subscriptions: BackgroundSubscriptionManager | None = None,
        gateway_internal_port: int = _DEFAULT_GATEWAY_INTERNAL_PORT,
        gateway_dispatch_url_provider: Callable[[], str | None] | None = None,
        product_default_model: str | None = None,
        relay_lifecycle_callback: RelayLifecycleCallback | None = None,
        kernel_event_observer: Callable[[Mapping[str, Any]], object] | None = None,
        bg_reply_sender: Callable[[str, ReplyContext, str], Awaitable[None]]
        | None = None,
        run_idle_timeout_seconds: float = _DEFAULT_RUN_IDLE_TIMEOUT_SECONDS,
        max_transition_locks: int = _MAX_SESSION_TRANSITION_LOCKS,
    ) -> None:
        if run_idle_timeout_seconds <= 0:
            raise ValueError("run_idle_timeout_seconds must be > 0")
        self._kernel = kernel
        self._session_binder = session_binder
        self._outbound_router = outbound_router
        self._run_queue = run_queue or SessionRunQueue()
        self._group_context_store = group_context_store
        self._image_resolver = image_resolver or ImageAttachmentResolver()
        self._background_subscriptions = background_subscriptions
        self._gateway_internal_port = gateway_internal_port
        self._gateway_dispatch_url_provider = gateway_dispatch_url_provider
        self._product_default_model = product_default_model
        self._relay_lifecycle_callback = relay_lifecycle_callback
        self._kernel_event_observer = kernel_event_observer
        self._bg_reply_sender = bg_reply_sender
        self._run_idle_timeout_seconds = run_idle_timeout_seconds
        self._active_runs: dict[str, _ActiveRunHandle] = {}
        self._steered_requests: dict[str, list[InboundRunRequest]] = {}
        self._user_interrupted_runs: set[str] = set()
        self._transition_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._transition_lock_users: dict[str, int] = {}
        self._max_transition_locks = max(1, max_transition_locks)

    async def dispatch(self, request: InboundRunRequest) -> PipelineResult:
        """Admit one normal message through steer or per-session FIFO.

        Args:
            request: Fully routed immutable operation snapshot.

        Returns:
            Observable result of the injected message or completed queued run.

        Raises:
            SessionRunQueueSealed: When Gateway shutdown has closed admission.
        """

        fallback_parts: list[dict[str, Any]] | None = None
        injected_result: PipelineResult | None = None
        image_failure: tuple[str, SessionBinding] | None = None
        async with self._transition(request.session_key):
            active = self._active_runs.get(request.session_key)
            if active is not None:
                binding = active.binding
                parts, failure_kind = await self._build_message_parts(request)
                if failure_kind is not None:
                    image_failure = (failure_kind, binding)
                else:
                    record = self._kernel.submit(
                        session_id=binding.kernel_session_id,
                        parts=parts,
                        workspace_root=active.agent.config.workspace_root,
                        steer=True,
                        model=self._resolve_agent_model(active.agent),
                    )
                    if getattr(record, "injected", False):
                        self._steered_requests.setdefault(active.run_id, []).append(
                            request
                        )
                        injected_result = PipelineResult(
                            agent_id=request.agent.agent_id,
                            session_key=request.session_key,
                            kernel_session_id=binding.kernel_session_id,
                            run_id=record.run_id,
                            reply_text="",
                            outbound=None,
                        )
                    else:
                        fallback_parts = parts
        if image_failure is not None:
            failure_kind, binding = image_failure
            return await self._reply_image_failure(
                failure_kind, request=request, binding=binding
            )
        if injected_result is not None:
            await self._emit_lifecycle(
                request.message,
                RelayLifecycleUpdate(
                    phase="accepted",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=injected_result.run_id,
                    kernel_session_id=injected_result.kernel_session_id,
                ),
            )
            return injected_result
        return await self._submit_queued(request, prebuilt_parts=fallback_parts)

    async def stop(self, request: StopRunRequest) -> PipelineResult:
        """Interrupt the complete active marker or return the existing idle result."""

        binding: SessionBinding | None = None
        active_run_id: str | None = None
        async with self._transition(request.session_key):
            active = self._active_runs.get(request.session_key)
            active_run_id = active.run_id if active is not None else None
            if active is None and request.message.is_group:
                return PipelineResult(
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    kernel_session_id="",
                    run_id="",
                    reply_text="",
                    outbound=None,
                )
            binding = (
                active.binding
                if active is not None
                else await self._ensure_binding_for_stop(request)
            )
            if active is not None:
                # This order is the user-stop attribution contract. The original
                # stream consumer performs reconcile after Kernel interruption.
                self._user_interrupted_runs.add(active_run_id)
                self._kernel.interrupt(binding.kernel_session_id)
                self._kernel.append_message(
                    session_id=binding.kernel_session_id,
                    role="user",
                    content="[Request interrupted by user for tool use]",
                    workspace_root=active.agent.config.workspace_root,
                )
        assert binding is not None
        if active_run_id is None:
            reply_text = "当前没有正在执行的操作。"
            ack_tag = "stop-noop"
        else:
            reply_text = "已停止当前操作。"
            ack_tag = "stop-ack"
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=request.agent.agent_id,
            ack_tag=ack_tag,
            source_message=request.message,
        )
        return PipelineResult(
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id=active_run_id or "",
            reply_text=reply_text,
            outbound=outbound,
        )

    def is_session_busy(self, session_key: str) -> bool:
        """Return whether a session owns queued/admitting work or an active run."""

        return (
            self._run_queue.is_active(session_key) or session_key in self._active_runs
        )

    def seal(self) -> None:
        """Synchronously reject new runs and subscriptions without waiting."""

        self._run_queue.seal_and_cancel_pending()
        if self._background_subscriptions is not None:
            self._background_subscriptions.seal()

    async def settle_admission(self, deadline: float) -> None:
        """Settle queued submit-or-rollback transitions by one absolute deadline."""

        await self._run_queue.settle_admission(deadline)

    async def drain(self, deadline: float) -> None:
        """Drain queue workers and subscribers without one owner skipping the other."""

        operations: list[tuple[str, Awaitable[None]]] = [
            ("queue", self._run_queue.drain_workers(deadline))
        ]
        if self._background_subscriptions is not None:
            operations.append(
                ("subscriptions", self._background_subscriptions.aclose(deadline))
            )
        results = await asyncio.gather(
            *(operation for _, operation in operations), return_exceptions=True
        )
        failures = [
            f"{name}: {result}"
            for (name, _), result in zip(operations, results, strict=True)
            if isinstance(result, BaseException)
        ]
        if failures:
            raise RuntimeError("coordinator drain failed: " + "; ".join(failures))

    async def _submit_queued(
        self,
        request: InboundRunRequest,
        *,
        prebuilt_parts: list[dict[str, Any]] | None,
    ) -> PipelineResult:
        admission_event = asyncio.Event()

        async def _on_cancel(error: GatewayShutdownBeforeSubmit) -> None:
            await self._emit_lifecycle(
                request.message,
                RelayLifecycleUpdate(
                    phase="failed",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    error=error.reason,
                ),
            )

        try:
            return await self._run_queue.submit(
                request.session_key,
                lambda: self._run_turn(
                    request,
                    prebuilt_parts=prebuilt_parts,
                    admission_event=admission_event,
                ),
                on_cancel=_on_cancel,
                admission_event=admission_event,
            )
        except SessionRunQueueSealed:
            await self._emit_lifecycle(
                request.message,
                RelayLifecycleUpdate(
                    phase="failed",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    error=GatewayShutdownBeforeSubmit.reason,
                ),
            )
            raise

    async def _run_turn(
        self,
        request: InboundRunRequest,
        *,
        prebuilt_parts: list[dict[str, Any]] | None,
        admission_event: asyncio.Event,
    ) -> PipelineResult:
        run_id: str | None = None
        binding: SessionBinding | None = None
        terminal_followers: tuple[InboundRunRequest, ...] = ()
        active_closed = False
        try:
            failure_kind: str | None = None
            async with self._transition(request.session_key):
                binding = await self._ensure_binding(request)
                if prebuilt_parts is None:
                    parts, failure_kind = await self._build_message_parts(request)
                else:
                    parts = prebuilt_parts
                if failure_kind is None:
                    # submit() is synchronous. Marker publication is the very next
                    # statement under the same lock: stop/steer cannot see half admission.
                    record = self._kernel.submit(
                        session_id=binding.kernel_session_id,
                        parts=parts,
                        workspace_root=request.agent.config.workspace_root,
                        model=self._resolve_model(request),
                    )
                    run_id = record.run_id
                    anchor_sequence = record.start_sequence
                    if run_id:
                        self._active_runs[request.session_key] = _ActiveRunHandle(
                            run_id=run_id,
                            binding=binding,
                            agent=request.agent,
                        )
                    admission_event.set()
            if failure_kind is not None:
                result = await self._reply_image_failure(
                    failure_kind, request=request, binding=binding
                )
                admission_event.set()
                return result
            assert binding is not None
            await self._emit_lifecycle(
                request.message,
                RelayLifecycleUpdate(
                    phase="accepted",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=run_id,
                    kernel_session_id=binding.kernel_session_id,
                ),
            )
            run_state, reply_text = await self._await_terminal_run(
                kernel_session_id=binding.kernel_session_id,
                run_id=run_id or "",
                anchor_sequence=anchor_sequence,
                on_other=lambda event: self._on_other_event(event, binding=binding),
            )
            terminal_followers = await self._close_active_run(
                session_key=request.session_key,
                run_id=run_id or "",
            )
            active_closed = True
            if self._background_subscriptions is not None:
                await self._background_subscriptions.ensure_after_foreground_terminal(
                    BackgroundSubscriptionRequest(
                        session_id=binding.kernel_session_id,
                        after_sequence=anchor_sequence or 0,
                        reply_context=binding.reply_context,
                        agent_id=request.agent.agent_id,
                    )
                )
            await self._emit_lifecycle(
                request.message,
                RelayLifecycleUpdate(
                    phase="running",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=run_id,
                    reply_text=reply_text,
                ),
            )
            outbound, detail = self._deliver_final_reply(
                request=request,
                binding=binding,
                run_id=run_id or "",
                run_state=run_state,
                reply_text=reply_text,
            )
            result = PipelineResult(
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id=run_id or "",
                reply_text=reply_text,
                outbound=outbound,
            )
            completed = RelayLifecycleUpdate(
                phase="completed",
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                run_id=run_id,
                reply_text=reply_text,
                detail=detail,
                usage=self._extract_usage(run_state),
            )
            await self._emit_lifecycle(request.message, completed)
            await self._emit_follower_lifecycle(terminal_followers, completed)
            return result
        except asyncio.CancelledError:
            try:
                if run_id and not active_closed:
                    terminal_followers = await self._close_active_run(
                        session_key=request.session_key,
                        run_id=run_id,
                    )
                    active_closed = True
                failed = RelayLifecycleUpdate(
                    phase="failed",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=run_id,
                    error=_SHUTDOWN_ACTIVE_RUN_CANCELLED,
                )
                await self._emit_lifecycle(request.message, failed)
                await self._emit_follower_lifecycle(terminal_followers, failed)
            finally:
                admission_event.set()
            raise
        except Exception as exc:
            try:
                if run_id and not active_closed:
                    terminal_followers = await self._close_active_run(
                        session_key=request.session_key,
                        run_id=run_id,
                    )
                    active_closed = True
                failed = RelayLifecycleUpdate(
                    phase="failed",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=run_id,
                    error=str(exc),
                )
                await self._emit_lifecycle(request.message, failed)
                await self._emit_follower_lifecycle(terminal_followers, failed)
            finally:
                admission_event.set()
            raise
        finally:
            if run_id and not active_closed:
                await self._close_active_run(
                    session_key=request.session_key,
                    run_id=run_id,
                )

    async def _close_active_run(
        self, *, session_key: str, run_id: str
    ) -> tuple[InboundRunRequest, ...]:
        """Atomically stop steer admission and capture every accepted follower."""

        async with self._transition(session_key):
            active = self._active_runs.get(session_key)
            if active is not None and active.run_id == run_id:
                self._active_runs.pop(session_key, None)
            self._user_interrupted_runs.discard(run_id)
            return tuple(self._steered_requests.pop(run_id, ()))

    async def _emit_follower_lifecycle(
        self,
        followers: tuple[InboundRunRequest, ...],
        update: RelayLifecycleUpdate,
    ) -> None:
        for follower in followers:
            await self._emit_lifecycle(
                follower.message,
                replace(
                    update,
                    agent_id=follower.agent.agent_id,
                    session_key=follower.session_key,
                ),
            )

    async def _on_other_event(
        self, event: Mapping[str, object], *, binding: SessionBinding
    ) -> None:
        if event.get("origin") in {"user", None, ""}:
            return
        if event.get("event") != "assistant_message":
            return
        content = event.get("content")
        if (
            isinstance(content, str)
            and content.strip()
            and not self._suppress_reply(content.strip(), in_group=True)
        ):
            self._outbound_router.send_text(
                text=content.strip(), reply_context=binding.reply_context
            )

    def _deliver_final_reply(
        self,
        *,
        request: InboundRunRequest,
        binding: SessionBinding,
        run_id: str,
        run_state: Mapping[str, object],
        reply_text: str,
    ) -> tuple[OutboundMessage | None, Mapping[str, Any] | None]:
        if run_state.get("status") == "cancelled":
            return None, {"suppressed_by": "cancelled"}
        if self._suppress_reply(reply_text, in_group=request.message.is_group) or (
            _is_external_channel_inbound(request.message)
            and self._is_no_reply_token(reply_text)
        ):
            return None, {"suppressed_by": "no_reply_token"}
        reply_context = binding.reply_context
        if _is_external_channel_inbound(request.message):
            metadata = dict(reply_context.metadata)
            metadata.update(
                {
                    "reply_phase": "final",
                    "reply_dedupe_key": f"{run_id}:text:{reply_text.strip()}",
                }
            )
            feishu_message_id = request.message.metadata.get("feishu_message_id")
            if isinstance(feishu_message_id, str) and feishu_message_id.strip():
                metadata["feishu_message_id"] = feishu_message_id
            reply_context = replace(reply_context, metadata=metadata)
        return (
            self._outbound_router.send_text(
                text=reply_text, reply_context=reply_context
            ),
            None,
        )

    async def _build_message_parts(
        self, request: InboundRunRequest
    ) -> tuple[list[dict[str, Any]], str | None]:
        message = request.message
        buffered = (
            self._group_context_store.drain(
                build_group_context_key(message, request.agent.agent_id)
            )
            if message.is_group and self._group_context_store is not None
            else []
        )
        texts = [_format_sender_text(sender, text) for sender, text in buffered]
        texts.append(
            _format_sender_text(request.sender_label, message.text)
            if message.is_group
            else message.text
        )
        parts: list[dict[str, Any]] = [{"type": "text", "text": text} for text in texts]
        resolution = await self._image_resolver.resolve(
            message.metadata.get("attachments")
        )
        if resolution.failure is not None:
            return [], resolution.failure
        parts.extend(resolution.parts)
        return parts, None

    async def _ensure_binding(self, request: InboundRunRequest) -> SessionBinding:
        dispatch_url, fallback_port = self._dispatch_endpoint_metadata()
        return await self._session_binder.resolve(
            SessionBindingRequest(
                session_key=request.session_key,
                reply_context=build_reply_context(request.message),
                message=request.message,
                gateway_internal_port=fallback_port,
                gateway_dispatch_url=dispatch_url,
            ),
            request.agent,
        )

    async def _ensure_binding_for_stop(self, request: StopRunRequest) -> SessionBinding:
        dispatch_url, fallback_port = self._dispatch_endpoint_metadata()
        return await self._session_binder.resolve(
            SessionBindingRequest(
                session_key=request.session_key,
                reply_context=build_reply_context(request.message),
                message=request.message,
                gateway_internal_port=fallback_port,
                gateway_dispatch_url=dispatch_url,
            ),
            request.agent,
        )

    def _dispatch_endpoint_metadata(self) -> tuple[str | None, int | None]:
        provider = self._gateway_dispatch_url_provider
        if provider is None:
            return None, self._gateway_internal_port
        return provider(), None

    async def _reply_image_failure(
        self,
        failure_kind: str,
        *,
        request: InboundRunRequest,
        binding: SessionBinding,
    ) -> PipelineResult:
        reply_text = _IMAGE_FAILURE_MESSAGES[failure_kind]
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=request.agent.agent_id,
            ack_tag=f"image-error-{failure_kind}",
            source_message=request.message,
        )
        await self._emit_lifecycle(
            request.message,
            RelayLifecycleUpdate(
                phase="completed",
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                reply_text=reply_text,
                detail={"image_failure": failure_kind},
            ),
        )
        return PipelineResult(
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

    async def _deliver_control_reply(
        self,
        *,
        text: str,
        binding: SessionBinding,
        agent_id: str,
        ack_tag: str,
        source_message: InboundMessage,
    ) -> OutboundMessage | None:
        from_session_id = _control_ack_from_session_id(
            agent_id=agent_id,
            kernel_session_id=binding.kernel_session_id,
            ack_tag=ack_tag,
            source_message=source_message,
        )
        if self._bg_reply_sender is not None:
            try:
                await self._bg_reply_sender(
                    text, binding.reply_context, from_session_id
                )
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning(
                    "control reply delivery via bg_reply_sender failed: %s", exc
                )
            return None
        return self._outbound_router.send_text(
            text=text, reply_context=binding.reply_context
        )

    async def _emit_lifecycle(
        self, message: InboundMessage, update: RelayLifecycleUpdate
    ) -> None:
        if self._relay_lifecycle_callback is not None:
            await self._relay_lifecycle_callback(message, update)

    async def _await_terminal_run(
        self,
        *,
        kernel_session_id: str,
        run_id: str,
        anchor_sequence: int | None,
        on_other: Callable[[Mapping[str, object]], Awaitable[None] | None],
    ) -> tuple[Mapping[str, object], str]:
        reply_text = ""
        run_state: Mapping[str, object] | None = None
        stream = self._kernel.stream(
            kernel_session_id, after_sequence=anchor_sequence or 0
        )
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        anext(stream), timeout=self._run_idle_timeout_seconds
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    self._kernel.cancel(run_id)
                    await self._emit_terminal_reconcile(run_id, reason="stalled")
                    raise TimeoutError(
                        f"kernel run {run_id} produced no events for "
                        f"{self._run_idle_timeout_seconds:g}s"
                    ) from None
                if event.get("run_id") != run_id:
                    result = on_other(event)
                    if asyncio.iscoroutine(result):
                        await result
                    continue
                if self._kernel_event_observer is not None:
                    result = self._kernel_event_observer(event)
                    if asyncio.iscoroutine(result):
                        await result
                if event.get("event") == "assistant_message":
                    content = event.get("content")
                    if isinstance(content, str):
                        reply_text = content
                elif (
                    event.get("event") == "run_status"
                    and event.get("status") in TERMINAL_RUN_STATUSES
                ):
                    run_state = event
                    break
        finally:
            close_stream = getattr(stream, "aclose", None)
            if callable(close_stream):
                await close_stream()
        if run_state is None:
            user_stopped = run_id in self._user_interrupted_runs
            await self._emit_terminal_reconcile(run_id, reason="interrupted")
            if user_stopped:
                return {"status": "cancelled"}, reply_text
            raise RuntimeError("stream ended without terminal run_status")
        status = run_state.get("status")
        if status == "cancelled":
            user_stopped = run_id in self._user_interrupted_runs
            await self._emit_terminal_reconcile(run_id, reason="interrupted")
            if user_stopped:
                return run_state, reply_text
            raise RuntimeError(self._extract_run_error(run_state, str(status)))
        if status != "completed":
            await self._emit_terminal_reconcile(run_id, reason="interrupted")
            raise RuntimeError(self._extract_run_error(run_state, str(status or "")))
        return run_state, reply_text

    async def _emit_terminal_reconcile(self, run_id: str, *, reason: str) -> None:
        if self._kernel_event_observer is None:
            return
        user_stopped = run_id in self._user_interrupted_runs
        event: dict[str, object] = {
            "event": "run_terminal_reconcile",
            "run_id": run_id,
            "reason": reason,
            "finalize_bubble": True,
            "delivery_status": "completed" if user_stopped else "failed",
        }
        if user_stopped:
            event.update(
                {
                    "content": USER_INTERRUPT_RECOVERY_CONTENT,
                }
            )
        result = self._kernel_event_observer(event)
        if asyncio.iscoroutine(result):
            await result

    def _transition_lock_for(self, session_key: str) -> asyncio.Lock:
        lock = self._transition_locks.get(session_key)
        if lock is None:
            lock = asyncio.Lock()
            self._transition_locks[session_key] = lock
        else:
            self._transition_locks.move_to_end(session_key)
        return lock

    @asynccontextmanager
    async def _transition(self, session_key: str) -> AsyncIterator[None]:
        """Lease one stable session lock across acquisition, use, and waiters."""

        lock = self._transition_lock_for(session_key)
        self._transition_lock_users[session_key] = (
            self._transition_lock_users.get(session_key, 0) + 1
        )
        self._trim_transition_locks()
        try:
            async with lock:
                yield
        finally:
            remaining = self._transition_lock_users[session_key] - 1
            if remaining:
                self._transition_lock_users[session_key] = remaining
            else:
                self._transition_lock_users.pop(session_key, None)
            self._trim_transition_locks()

    def _trim_transition_locks(self) -> None:
        while len(self._transition_locks) > self._max_transition_locks:
            removable = next(
                (
                    session_key
                    for session_key, lock in self._transition_locks.items()
                    if self._transition_lock_users.get(session_key, 0) == 0
                    and not lock.locked()
                ),
                None,
            )
            if removable is None:
                break
            self._transition_locks.pop(removable, None)

    def _resolve_model(self, request: InboundRunRequest) -> str | None:
        return self._resolve_agent_model(request.agent)

    def _resolve_agent_model(self, agent: LiveAgentSnapshot) -> str | None:
        return resolve_run_model(agent.config, product_default=self._product_default_model)

    @staticmethod
    def _is_no_reply_token(text: str) -> bool:
        return is_protocol_silence_token(text)

    @staticmethod
    def _suppress_reply(reply_text: str, *, in_group: bool) -> bool:
        policy = (
            ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS
            if in_group
            else ReplyVisibilityPolicy.LITERAL_TEXT
        )
        return should_suppress_reply(reply_text, policy=policy)

    @staticmethod
    def _extract_run_error(
        run_state: Mapping[str, object], fallback_status: str
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
    def _extract_usage(run_state: Mapping[str, object]) -> Mapping[str, int] | None:
        usage = run_state.get("usage")
        if not isinstance(usage, Mapping):
            return None
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        total = usage.get("total_tokens")
        if not isinstance(prompt, int) or not isinstance(completion, int):
            return None
        if not isinstance(total, int):
            total = prompt + completion
        return {
            "prompt_tokens": max(prompt, 0),
            "completion_tokens": max(completion, 0),
            "total_tokens": max(total, 0),
        }


def _format_sender_text(sender: str, text: str) -> str:
    normalized = sender.strip()
    return f"[{normalized}] {text}" if normalized else text


def _control_ack_from_session_id(
    *,
    agent_id: str,
    kernel_session_id: str,
    ack_tag: str,
    source_message: InboundMessage,
) -> str:
    """Build the stable IM dispatch key for one visible control acknowledgement."""

    base = f"{agent_id}|tool_call:{kernel_session_id}:{ack_tag}"
    source_id = _control_ack_source_id(source_message)
    if source_id is None:
        return base
    return f"{base}:{source_id}"


def _control_ack_source_id(message: InboundMessage) -> str | None:
    for key in ("feishu_message_id", "relay_task_id", "idempotency_key", "message_id"):
        value = message.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_dispatch_id_part(value)
    return None


def _normalize_dispatch_id_part(value: str) -> str:
    normalized = "_".join(value.strip().split()).replace("|", "_")
    return normalized[:160] if len(normalized) > 160 else normalized


def _is_external_channel_inbound(message: InboundMessage) -> bool:
    trigger_source = message.metadata.get("trigger_source")
    return isinstance(trigger_source, str) and trigger_source.strip() not in {"", "im"}
