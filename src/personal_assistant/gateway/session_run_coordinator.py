"""Own Gateway per-session run admission, interruption, and terminal cleanup."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agent.sdk import (
    TERMINAL_RUN_STATUSES,
    USER_INTERRUPT_RECOVERY_CONTENT,
    RunOrigin,
    SessionRuntimeConfig,
    WorkflowControlAction,
    WorkflowSaveScope,
)

from personal_assistant.config.local_store import resolve_run_model
from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.gateway.session_composition import project_agent_runtime

from personal_assistant.channels.base import (
    InboundMessage,
    OutboundMessage,
    ReplyContext,
)
from personal_assistant.gateway.background_subscriptions import (
    BackgroundSubscriptionManager,
    BackgroundSubscriptionRequest,
)
from personal_assistant.gateway.agent_catalog import LiveAgentSnapshot
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.human_message_context import (
    FrozenHumanMessageContext,
    PaTimeContext,
    apply_frozen_header,
)
from personal_assistant.gateway.image_attachments import ImageAttachmentResolver
from personal_assistant.gateway.inbound_models import (
    CompactSessionRequest,
    EffortCommandRequest,
    InboundRunRequest,
    NewSessionRequest,
    PipelineResult,
    RelayLifecycleCallback,
    RelayLifecycleUpdate,
    RoutedInbound,
    StopRunRequest,
    WorkflowCommandRequest,
    build_group_context_key,
)
from personal_assistant.gateway.workflow_commands import (
    WorkflowCommand,
    format_workflow_run,
    format_workflow_runs,
    parse_workflow_command,
)
from personal_assistant.gateway.effort_commands import (
    EffortCommand,
    parse_effort_command,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.runtime_footer import ExternalFinalProjection
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
from personal_assistant.gateway.readable_input_projection import (
    ReadableInputProjectionStore,
)
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import (
    BoundaryIntent,
    ControlOperation,
    PendingBoundaryIntent,
    SessionBinding,
    build_reply_context,
)
from personal_assistant.gateway.boundary_outbox import BoundaryOutboxDispatcher
from personal_assistant.gateway.shadow_saga import ExternalShadowOutput

if TYPE_CHECKING:
    from agent.sdk import Kernel


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


@dataclass(frozen=True, slots=True)
class _MessagePartsProjection:
    """Carry model parts and both exact text fallbacks for one admission."""

    model_parts: list[dict[str, Any]]
    model_fallback: str
    readable_fallback: str


@dataclass(frozen=True, slots=True)
class AcceptedRecoveryFollower:
    """Associate one accepted Gateway follower with its Kernel pending identity."""

    pending_id: str
    request: InboundRunRequest


@dataclass(frozen=True, slots=True)
class RecoveryHandoffClaim:
    """Describe one validated user continuation batch adopted by the Gateway."""

    run_id: str
    recovery_id: str
    batch_index: int
    followers: tuple[AcceptedRecoveryFollower, ...]


class RecoveryHandoffError(RuntimeError):
    """Report an authoritative but invalid or unavailable recovery handoff."""


class RecoveryHandoffLedger:
    """Validate one old-run follower suffix through successor settlement."""

    def __init__(
        self,
        *,
        predecessor_run_id: str,
        followers: tuple[AcceptedRecoveryFollower, ...],
    ) -> None:
        self.predecessor_run_id = predecessor_run_id
        self._remaining = list(followers)
        self._recovery_id: str | None = None
        self._successor_run_ids: list[str] = []
        self._batch_indexes: set[int] = set()
        self._settled = False
        self._closed = False

    @property
    def remaining_followers(self) -> tuple[AcceptedRecoveryFollower, ...]:
        """Return the follower suffix not yet claimed by a successor."""

        return tuple(self._remaining)

    @property
    def successor_run_ids(self) -> tuple[str, ...]:
        """Return every linked successor observed before settlement."""

        return tuple(self._successor_run_ids)

    def close(self) -> tuple[AcceptedRecoveryFollower, ...]:
        """Fence the ledger and return followers that still need failure closure."""

        if self._closed:
            return ()
        self._closed = True
        remaining = tuple(self._remaining)
        self._remaining.clear()
        return remaining

    def observe_successor(
        self, event: Mapping[str, object]
    ) -> RecoveryHandoffClaim | None:
        """Validate and claim one continuation queued event when it is user-owned."""

        if self._closed or self._settled:
            return None
        continuation = event.get("continuation")
        if not isinstance(continuation, Mapping):
            return None
        predecessor = continuation.get("predecessor_run_id")
        if predecessor != self.predecessor_run_id:
            return None
        run_id = event.get("run_id")
        recovery_id = continuation.get("recovery_id")
        batch_index = continuation.get("batch_index")
        origin = continuation.get("origin")
        pending_ids = continuation.get("pending_ids")
        if (
            not isinstance(run_id, str)
            or not run_id
            or not isinstance(recovery_id, str)
            or not recovery_id
            or not isinstance(batch_index, int)
            or isinstance(batch_index, bool)
            or batch_index < 0
            or not isinstance(origin, str)
            or not isinstance(pending_ids, list)
            or not pending_ids
            or any(not isinstance(item, str) or not item for item in pending_ids)
        ):
            raise RecoveryHandoffError("invalid continuation descriptor")
        if self._recovery_id is None:
            self._recovery_id = recovery_id
        elif recovery_id != self._recovery_id:
            raise RecoveryHandoffError("recovery id mismatch")
        if run_id in self._successor_run_ids or batch_index in self._batch_indexes:
            return None
        self._successor_run_ids.append(run_id)
        self._batch_indexes.add(batch_index)
        if origin != "user":
            return None

        expected = [item.pending_id for item in self._remaining[: len(pending_ids)]]
        if pending_ids != expected:
            raise RecoveryHandoffError("user continuation pending ids mismatch")
        claimed = tuple(self._remaining[: len(pending_ids)])
        del self._remaining[: len(pending_ids)]
        return RecoveryHandoffClaim(
            run_id=run_id,
            recovery_id=recovery_id,
            batch_index=batch_index,
            followers=claimed,
        )

    def observe_settlement(self, event: Mapping[str, object]) -> bool:
        """Validate the exactly-once authoritative settlement for this recovery."""

        if self._closed or self._settled:
            return False
        if event.get("predecessor_run_id") != self.predecessor_run_id:
            return False
        recovery_id = event.get("recovery_id")
        if not isinstance(recovery_id, str) or not recovery_id:
            raise RecoveryHandoffError("invalid recovery settlement")
        if self._recovery_id is not None and recovery_id != self._recovery_id:
            raise RecoveryHandoffError("recovery settlement id mismatch")
        self._recovery_id = recovery_id
        outcome = event.get("outcome")
        if outcome != "scheduled":
            raise RecoveryHandoffError(f"recovery settlement {outcome}")
        successor_run_ids = event.get("successor_run_ids")
        if successor_run_ids != self._successor_run_ids:
            raise RecoveryHandoffError("recovery successor ids mismatch")
        if self._remaining:
            raise RecoveryHandoffError("recovery left unclaimed pending ids")
        self._settled = True
        return True


@dataclass(slots=True)
class _RecoveryHandoffState:
    """Keep one predecessor ledger reachable by shutdown and control cleanup."""

    ledger: RecoveryHandoffLedger
    claims: dict[str, RecoveryHandoffClaim]
    completed_run_ids: set[str]
    control_event: asyncio.Event


@dataclass(slots=True)
class _CompactReservation:
    """Hold one FIFO slot while inbound metadata is prepared."""

    session_key: str
    agent_id: str
    generation: int
    request: asyncio.Future[CompactSessionRequest | None]
    result: asyncio.Future[PipelineResult] | None = None
    released: bool = False


def _build_routed_reply_context(routed: RoutedInbound) -> ReplyContext:
    """Project an anchored IM shadow target into the durable reply context."""

    reply_context = build_reply_context(routed.message)
    shadow_ref = routed.shadow.ref
    if shadow_ref is None:
        return reply_context
    return replace(
        reply_context,
        metadata={
            **reply_context.metadata,
            "shadow_conversation_id": shadow_ref.conversation_id,
        },
    )


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
        reasoning_catalog: ModelReasoningCatalog | None = None,
        relay_lifecycle_callback: RelayLifecycleCallback | None = None,
        kernel_event_observer: Callable[[Mapping[str, Any]], object] | None = None,
        external_final_projection_provider: (
            Callable[[str], ExternalFinalProjection | None] | None
        ) = None,
        shadow_output_prepare: (
            Callable[[str, str, str, str | None, str], ExternalShadowOutput] | None
        ) = None,
        bg_reply_sender: Callable[[str, ReplyContext, str], Awaitable[None]]
        | None = None,
        node_id: str | None = None,
        boundary_outbox: BoundaryOutboxDispatcher | None = None,
        suppress_run_delivery: Callable[[str], None] | None = None,
        quiesce_run_delivery: Callable[[str], Awaitable[None]] | None = None,
        restore_run_delivery: Callable[[str], None] | None = None,
        commit_run_delivery: Callable[[str], Awaitable[None]] | None = None,
        drain_external_control_deliveries: Callable[[], Awaitable[None]] | None = None,
        update_workflow_size_guideline: Callable[[str, str], None] | None = None,
        run_idle_timeout_seconds: float = _DEFAULT_RUN_IDLE_TIMEOUT_SECONDS,
        max_transition_locks: int = _MAX_SESSION_TRANSITION_LOCKS,
        readable_input_projection_store: ReadableInputProjectionStore | None = None,
        time_context: PaTimeContext | None = None,
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
        self._reasoning_catalog = reasoning_catalog
        self._relay_lifecycle_callback = relay_lifecycle_callback
        self._kernel_event_observer = kernel_event_observer
        self._external_final_projection_provider = external_final_projection_provider
        self._shadow_output_prepare = shadow_output_prepare
        self._bg_reply_sender = bg_reply_sender
        self._node_id = node_id
        self._boundary_outbox = boundary_outbox
        self._suppress_run_delivery = suppress_run_delivery
        self._quiesce_run_delivery = quiesce_run_delivery
        self._restore_run_delivery = restore_run_delivery
        self._commit_run_delivery = commit_run_delivery
        self._drain_external_control_deliveries = drain_external_control_deliveries
        self._update_workflow_size_guideline = update_workflow_size_guideline
        self._run_idle_timeout_seconds = run_idle_timeout_seconds
        self._active_runs: dict[str, _ActiveRunHandle] = {}
        self._steered_requests: dict[str, list[AcceptedRecoveryFollower]] = {}
        self._consumed_steer_counts: dict[str, int] = {}
        self._recovery_handoffs: dict[str, _RecoveryHandoffState] = {}
        self._terminalized_recovery_roots: set[str] = set()
        self._queued_compactions: dict[str, int] = {}
        self._user_interrupted_runs: set[str] = set()
        self._reset_suppressed_runs: set[str] = set()
        self._session_generations: dict[str, int] = {}
        self._transition_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._transition_lock_users: dict[str, int] = {}
        self._max_transition_locks = max(1, max_transition_locks)
        self._readable_input_projection_store = readable_input_projection_store
        self._time_context = time_context

    async def dispatch(self, request: InboundRunRequest) -> PipelineResult:
        """Admit one normal message through steer or per-session FIFO.

        Args:
            request: Fully routed immutable operation snapshot.

        Returns:
            Observable result of the injected message or completed queued run.

        Raises:
            SessionRunQueueSealed: When Gateway shutdown has closed admission.
        """

        fallback_projection: _MessagePartsProjection | None = None
        injected_result: PipelineResult | None = None
        image_failure: tuple[str, SessionBinding] | None = None
        async with self._transition(request.session_key):
            request = replace(
                request,
                generation=self._session_generations.get(request.session_key, 0),
            )
            active = self._active_runs.get(request.session_key)
            if active is not None and not self._queued_compactions.get(
                request.session_key, 0
            ):
                binding = active.binding
                projection, failure_kind = await self._build_message_parts(request)
                if failure_kind is not None:
                    image_failure = (failure_kind, binding)
                else:
                    record = self._kernel.try_steer(
                        session_id=binding.kernel_session_id,
                        parts=projection.model_parts,
                        expected_run_id=active.run_id,
                    )
                    if record is not None:
                        if record.run_id != active.run_id:
                            raise RuntimeError(
                                "Kernel accepted steer for a different active run: "
                                f"expected={active.run_id}, actual={record.run_id}"
                            )
                        self._steered_requests.setdefault(active.run_id, []).append(
                            AcceptedRecoveryFollower(
                                pending_id=record.pending_id,
                                request=request,
                            )
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
                        fallback_projection = projection
        if image_failure is not None:
            failure_kind, binding = image_failure
            return await self._reply_image_failure(
                failure_kind, request=request, binding=binding
            )
        if injected_result is not None:
            await self._emit_lifecycle(
                request.routed,
                RelayLifecycleUpdate(
                    phase="accepted",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=injected_result.run_id,
                    kernel_session_id=injected_result.kernel_session_id,
                ),
            )
            return injected_result
        return await self._submit_queued(
            request, prebuilt_projection=fallback_projection
        )

    async def new_session(self, request: NewSessionRequest) -> PipelineResult:
        """Replace one chat binding with a fresh session under its transition lock."""

        reply_text = "已开始新会话。"
        active_run_id: str | None = None
        quiesced_run_id: str | None = None
        async with self._transition(request.session_key):
            if request.operation_id is not None:
                completed = self._session_binder.completed_control(
                    session_key=request.session_key,
                    operation_id=request.operation_id,
                    kind="new",
                )
                if completed is not None:
                    if completed.status != "completed":
                        return await self._new_session_failure(
                            request, reply_text=completed.reply_text, persist=False
                        )
                    binding = self._session_binder.lookup(request.session_key)
                    if binding is None:
                        raise RuntimeError("completed reset lost its session binding")
                    outbound = await self._deliver_control_reply(
                        text=completed.reply_text,
                        binding=binding,
                        agent_id=request.agent.agent_id,
                        ack_tag="new-ack",
                        source_routed=request.routed,
                        operation_id=request.operation_id,
                    )
                    return PipelineResult(
                        agent_id=request.agent.agent_id,
                        session_key=request.session_key,
                        kernel_session_id=completed.kernel_session_id,
                        run_id="",
                        reply_text=completed.reply_text,
                        outbound=outbound,
                    )
            agent = self._latest_agent(request.agent)
            runtime = self._project_runtime(agent=agent, message=request.message)
            dispatch_url, fallback_port = self._dispatch_endpoint_metadata()
            try:
                candidate = await self._session_binder.prepare_reset(
                    SessionBindingRequest(
                        session_key=request.session_key,
                        reply_context=_build_routed_reply_context(request.routed),
                        message=request.message,
                        gateway_internal_port=fallback_port,
                        gateway_dispatch_url=dispatch_url,
                        runtime=runtime.runtime,
                        profile_version=runtime.profile_version,
                    ),
                    agent,
                )
            except Exception:  # noqa: BLE001
                logging.getLogger(__name__).exception(
                    "fresh session preparation failed"
                )
                return await self._new_session_failure(request)
            active = self._active_runs.get(request.session_key)
            active_run_id = active.run_id if active is not None else None
            if active_run_id is not None:
                reply_text = "已停止当前操作，并已开始新会话。"
                if self._quiesce_run_delivery is not None:
                    await self._quiesce_run_delivery(active_run_id)
                    quiesced_run_id = active_run_id
            try:
                binding = self._session_binder.publish_reset(
                    candidate,
                    operation_id=request.operation_id,
                    superseded_run_id=active_run_id,
                    reply_text=reply_text,
                    external_saga_id=_external_shadow_saga_id(request.routed),
                )
            except Exception:
                if (
                    quiesced_run_id is not None
                    and self._restore_run_delivery is not None
                ):
                    self._restore_run_delivery(quiesced_run_id)
                logging.getLogger(__name__).exception(
                    "fresh session publication failed"
                )
                return await self._new_session_failure(request)
            self._session_generations[request.session_key] = (
                self._session_generations.get(request.session_key, 0) + 1
            )
            if active is not None:
                self._reset_suppressed_runs.add(active.run_id)
                self._fence_recovery_for_control(active.run_id, reset=True)
                self._active_runs.pop(request.session_key, None)
                if self._commit_run_delivery is not None:
                    await self._commit_run_delivery(active.run_id)
                elif self._suppress_run_delivery is not None:
                    self._suppress_run_delivery(active.run_id)
                self._kernel.interrupt(active.binding.kernel_session_id)
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=request.agent.agent_id,
            ack_tag="new-ack",
            source_routed=request.routed,
            operation_id=request.operation_id,
        )
        return PipelineResult(
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

    async def _new_session_failure(
        self,
        request: NewSessionRequest,
        *,
        reply_text: str = "未能开始新会话，当前会话保持不变。",
        persist: bool = True,
    ) -> PipelineResult:
        """Report a failed reset without claiming that the current binding changed."""

        if persist and request.operation_id is not None:
            reply_text = self._session_binder.complete_control(
                ControlOperation(
                    session_key=request.session_key,
                    operation_id=request.operation_id,
                    kind="new",
                    status="failed",
                    kernel_session_id="",
                    reply_text=reply_text,
                ),
                external_saga_id=_external_shadow_saga_id(request.routed),
            ).reply_text
        binding = self._session_binder.lookup(request.session_key)
        if binding is None:
            if (
                request.operation_id is not None
                and _external_shadow_saga_id(request.routed) is not None
                and self._drain_external_control_deliveries is not None
            ):
                try:
                    await self._drain_external_control_deliveries()
                except Exception:  # noqa: BLE001
                    logging.getLogger(__name__).exception(
                        "external failed-control delivery deferred for recovery"
                    )
                outbound = None
            else:
                outbound = self._outbound_router.send_text(
                    text=reply_text, reply_context=build_reply_context(request.message)
                )
            return PipelineResult(
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                kernel_session_id="",
                run_id="",
                reply_text=reply_text,
                outbound=outbound,
            )
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=request.agent.agent_id,
            ack_tag="new-failed",
            source_routed=request.routed,
            operation_id=request.operation_id,
        )
        return PipelineResult(
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

    def reserve_compact(
        self, *, session_key: str, agent_id: str
    ) -> _CompactReservation:
        """Reserve a compaction FIFO slot before external shadow preparation yields."""

        reservation = _CompactReservation(
            session_key=session_key,
            agent_id=agent_id,
            generation=self._session_generations.get(session_key, 0),
            request=asyncio.get_running_loop().create_future(),
        )
        self._queued_compactions[session_key] = (
            self._queued_compactions.get(session_key, 0) + 1
        )

        async def _on_cancel(_error: GatewayShutdownBeforeSubmit) -> None:
            self._release_compact_reservation(reservation)

        reservation.result = self._run_queue.enqueue(
            session_key,
            lambda: self._run_reserved_compact(reservation),
            on_cancel=_on_cancel,
        )
        return reservation

    async def commit_compact(
        self,
        reservation: _CompactReservation,
        request: CompactSessionRequest,
    ) -> PipelineResult:
        """Fill a reserved compact slot and await its FIFO outcome."""

        if request.session_key != reservation.session_key:
            raise ValueError("compact reservation session does not match request")
        if request.agent.agent_id != reservation.agent_id:
            raise ValueError("compact reservation agent does not match request")
        if not reservation.request.done():
            reservation.request.set_result(
                replace(request, generation=reservation.generation)
            )
        assert reservation.result is not None
        return await reservation.result

    def abandon_compact(self, reservation: _CompactReservation) -> None:
        """Release a reserved compact slot when inbound preparation fails."""

        if not reservation.request.done():
            reservation.request.set_result(None)

    async def compact(self, request: CompactSessionRequest) -> PipelineResult:
        """Queue compaction behind current session work without making it a turn."""

        reservation = self.reserve_compact(
            session_key=request.session_key,
            agent_id=request.agent.agent_id,
        )
        try:
            return await self.commit_compact(reservation, request)
        except BaseException:
            self.abandon_compact(reservation)
            raise

    async def _run_reserved_compact(
        self, reservation: _CompactReservation
    ) -> PipelineResult:
        """Wait for inbound preparation, then execute the reserved FIFO item."""

        try:
            request = await reservation.request
            if request is None:
                return PipelineResult(
                    agent_id=reservation.agent_id,
                    session_key=reservation.session_key,
                    kernel_session_id="",
                    run_id="",
                    reply_text="",
                    outbound=None,
                )
            return await self._run_queued_compact(request)
        finally:
            self._release_compact_reservation(reservation)

    def _release_compact_reservation(self, reservation: _CompactReservation) -> None:
        """Remove one barrier once its reserved queue item has settled."""

        if reservation.released:
            return
        reservation.released = True
        remaining = self._queued_compactions.get(reservation.session_key, 0) - 1
        if remaining > 0:
            self._queued_compactions[reservation.session_key] = remaining
        else:
            self._queued_compactions.pop(reservation.session_key, None)

    async def _run_queued_compact(
        self, request: CompactSessionRequest
    ) -> PipelineResult:
        """Run one FIFO compaction after preceding session work has settled."""

        binding: SessionBinding | None
        reply_text: str
        async with self._transition(request.session_key):
            binding = self._session_binder.lookup(request.session_key)
            completed = (
                self._session_binder.completed_control(
                    session_key=request.session_key,
                    operation_id=request.operation_id,
                    kind="compact",
                )
                if request.operation_id is not None
                else None
            )
            if completed is not None:
                reply_text = completed.reply_text
            elif request.generation != self._session_generations.get(
                request.session_key, 0
            ):
                reply_text = "已开始新会话，未执行之前的压缩请求。"
                if request.operation_id is not None:
                    reply_text = self._session_binder.complete_control(
                        ControlOperation(
                            session_key=request.session_key,
                            operation_id=request.operation_id,
                            kind="compact",
                            status="superseded",
                            kernel_session_id="",
                            reply_text=reply_text,
                        ),
                        external_saga_id=_external_shadow_saga_id(request.routed),
                    ).reply_text
            elif binding is None:
                reply_text = "当前历史不足，无需压缩。"
            else:
                agent = self._latest_agent(request.agent)
                try:
                    result = await self._kernel.compact(
                        binding.kernel_session_id,
                        workspace_root=agent.config.workspace_root,
                        focus=request.focus,
                        idempotency_key=request.operation_id,
                    )
                except Exception:  # noqa: BLE001
                    logging.getLogger(__name__).exception("manual compaction failed")
                    reply_text = "压缩未完成，当前会话保持不变。"
                else:
                    if result is None:
                        reply_text = "当前历史不足，无需压缩。"
                    elif request.focus:
                        reply_text = "已按关注点压缩当前会话。"
                    else:
                        reply_text = "已压缩当前会话。"
            if (
                request.operation_id is not None
                and completed is None
                and (
                    request.generation
                    == self._session_generations.get(request.session_key, 0)
                )
            ):
                reply_text = self._session_binder.complete_control(
                    ControlOperation(
                        session_key=request.session_key,
                        operation_id=request.operation_id,
                        kind="compact",
                        status="completed",
                        kernel_session_id=(
                            binding.kernel_session_id if binding else ""
                        ),
                        reply_text=reply_text,
                    ),
                    external_saga_id=_external_shadow_saga_id(request.routed),
                ).reply_text
        return await self._compact_result_reply(
            request=request, binding=binding, reply_text=reply_text
        )

    async def _compact_result_reply(
        self,
        *,
        request: CompactSessionRequest,
        binding: SessionBinding | None,
        reply_text: str,
    ) -> PipelineResult:
        """Deliver a compact outcome without allocating an empty session for no-op."""

        if binding is None:
            if (
                request.operation_id is not None
                and _external_shadow_saga_id(request.routed) is not None
                and self._drain_external_control_deliveries is not None
            ):
                try:
                    await self._drain_external_control_deliveries()
                except Exception:  # noqa: BLE001
                    logging.getLogger(__name__).exception(
                        "external control delivery deferred for recovery"
                    )
                outbound = None
            else:
                outbound = self._outbound_router.send_text(
                    text=reply_text, reply_context=build_reply_context(request.message)
                )
            return PipelineResult(
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                kernel_session_id="",
                run_id="",
                reply_text=reply_text,
                outbound=outbound,
            )
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=request.agent.agent_id,
            ack_tag="compact-ack",
            source_routed=request.routed,
            operation_id=request.operation_id,
        )
        return PipelineResult(
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

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
                self._fence_recovery_for_control(active_run_id, reset=False)
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
            source_routed=request.routed,
            operation_id=None,
        )
        return PipelineResult(
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id=active_run_id or "",
            reply_text=reply_text,
            outbound=outbound,
        )

    async def workflow_command(
        self, request: WorkflowCommandRequest
    ) -> PipelineResult | None:
        """Execute one active-Workflow slash command or leave unknown text alone."""

        agent = self._latest_agent(request.agent)
        if "Workflow" not in agent.config.tool_allowlist:
            return None
        named = self._kernel.list_named_workflows(
            workspace_root=agent.config.workspace_root
        )
        command = parse_workflow_command(
            request.command_text,
            named_workflows=tuple(
                f"{item.namespace}:{item.name}" if item.namespace else item.name
                for item in named
            ),
        )
        if command is None:
            return None
        if command.kind == "invoke":
            return await self.dispatch(
                InboundRunRequest(
                    routed=replace(
                        request.routed,
                        message=replace(
                            request.message,
                            text=_named_workflow_instruction(command),
                        ),
                    ),
                    agent=agent,
                    session_key=request.session_key,
                    sender_label=request.sender_label,
                )
            )

        async with self._transition(request.session_key):
            binding = self._session_binder.lookup(request.session_key)
            if binding is None:
                binding = await self._ensure_binding_for_command(request, agent=agent)
            control_kind = f"workflow:{command.kind}"
            completed = (
                self._session_binder.completed_control(
                    session_key=request.session_key,
                    operation_id=request.operation_id,
                    kind=control_kind,
                )
                if request.operation_id is not None
                else None
            )
            if completed is not None:
                reply_text = completed.reply_text
            else:
                reply_text = await self._execute_workflow_command(
                    command,
                    session_id=binding.kernel_session_id,
                    agent=agent,
                )
                if request.operation_id is not None:
                    reply_text = self._session_binder.complete_control(
                        ControlOperation(
                            session_key=request.session_key,
                            operation_id=request.operation_id,
                            kind=control_kind,
                            status="completed",
                            kernel_session_id=binding.kernel_session_id,
                            reply_text=reply_text,
                        ),
                        external_saga_id=_external_shadow_saga_id(request.routed),
                    ).reply_text
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=agent.agent_id,
            ack_tag="workflow-ack",
            source_routed=request.routed,
            operation_id=request.operation_id,
        )
        return PipelineResult(
            agent_id=agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

    async def effort_command(
        self, request: EffortCommandRequest
    ) -> PipelineResult | None:
        """Apply one model-capability-derived session effort command."""

        command = parse_effort_command(request.command_text)
        if command is None:
            return None
        agent = self._latest_agent(request.agent)
        async with self._transition(request.session_key):
            binding = self._session_binder.lookup(request.session_key)
            if binding is None:
                binding = await self._ensure_binding_for_command(request, agent=agent)
            completed = (
                self._session_binder.completed_control(
                    session_key=request.session_key,
                    operation_id=request.operation_id,
                    kind="effort",
                )
                if request.operation_id is not None
                else None
            )
            if completed is not None:
                reply_text = completed.reply_text
            else:
                state = await self._kernel.get_session_runtime(
                    session_id=binding.kernel_session_id,
                    workspace_root=agent.config.workspace_root,
                )
                if state is None:
                    reply_text = "推理档位命令未执行: 当前会话没有完整 runtime。"
                else:
                    baseline = self._project_runtime(
                        agent=agent, message=request.message
                    ).runtime
                    reply_text = await self._execute_effort_command(
                        command,
                        session_id=binding.kernel_session_id,
                        agent=agent,
                        runtime=self._reconcile_runtime(
                            baseline=baseline, persisted=state.runtime
                        ),
                    )
                if request.operation_id is not None:
                    reply_text = self._session_binder.complete_control(
                        ControlOperation(
                            session_key=request.session_key,
                            operation_id=request.operation_id,
                            kind="effort",
                            status="completed",
                            kernel_session_id=binding.kernel_session_id,
                            reply_text=reply_text,
                        ),
                        external_saga_id=_external_shadow_saga_id(request.routed),
                    ).reply_text
        outbound = await self._deliver_control_reply(
            text=reply_text,
            binding=binding,
            agent_id=agent.agent_id,
            ack_tag="effort-ack",
            source_routed=request.routed,
            operation_id=request.operation_id,
        )
        return PipelineResult(
            agent_id=agent.agent_id,
            session_key=request.session_key,
            kernel_session_id=binding.kernel_session_id,
            run_id="",
            reply_text=reply_text,
            outbound=outbound,
        )

    async def _execute_effort_command(
        self,
        command: EffortCommand,
        *,
        session_id: str,
        agent: LiveAgentSnapshot,
        runtime: SessionRuntimeConfig,
    ) -> str:
        """Validate and durably apply an effort selection to one session."""

        catalog = self._reasoning_catalog
        capability = (
            catalog.capability_for(runtime.model) if catalog is not None else None
        )
        if capability is None or capability.kind != "selectable":
            return f"当前模型 {runtime.model} 不支持可选推理档位。"
        supports_ultracode = (
            "Workflow" in runtime.enabled_tools and "xhigh" in capability.levels
        )
        allowed = list(capability.levels)
        if supports_ultracode:
            allowed.append("ultracode")
        if command.value not in allowed:
            return f"当前模型 {runtime.model} 可用的推理档位: {'、'.join(allowed)}。"
        ultracode = command.value == "ultracode"
        requested = "xhigh" if ultracode else command.value
        assert requested is not None
        await self._kernel.reconfigure_session(
            session_id=session_id,
            workspace_root=agent.config.workspace_root,
            runtime=replace(
                runtime,
                reasoning_effort=catalog.resolve(runtime.model, requested),
                reasoning_effort_override=requested,
                workflow_ultracode=ultracode,
            ),
        )
        if ultracode:
            return "Ultracode 已开启。"
        return f"已将当前会话的推理档位设为 {requested}。"

    async def _execute_workflow_command(
        self,
        command: WorkflowCommand,
        *,
        session_id: str,
        agent: LiveAgentSnapshot,
    ) -> str:
        if command.kind == "error":
            return command.error or "Workflow 命令无效。"
        try:
            if command.kind == "list":
                return format_workflow_runs(
                    self._kernel.list_workflow_runs(session_id=session_id)
                )
            if command.kind == "detail":
                run = self._kernel.get_workflow_run(
                    session_id=session_id, run_id=command.run_id or ""
                )
                return (
                    format_workflow_run(run)
                    if run is not None
                    else f"未找到 Workflow 运行: {command.run_id}"
                )
            if command.kind == "control":
                run = self._kernel.control_workflow(
                    session_id=session_id,
                    run_id=command.run_id or "",
                    action=WorkflowControlAction(command.action or ""),
                    agent_call_id=command.agent_call_id,
                )
                return format_workflow_run(run)
            if command.kind == "save":
                saved = self._kernel.save_workflow(
                    session_id=session_id,
                    run_id=command.run_id or "",
                    scope=WorkflowSaveScope(command.scope or ""),
                    name=command.name,
                )
                return f"已保存 Workflow /{saved.name}\n路径: {saved.path}"
            if command.kind == "config":
                if self._update_workflow_size_guideline is None:
                    raise RuntimeError("Workflow config owner is unavailable")
                self._update_workflow_size_guideline(
                    agent.agent_id, command.guideline or "medium"
                )
                return (
                    "已将 workflowSizeGuideline 设为 "
                    f"{command.guideline}；从下一轮起生效。"
                )
        except (RuntimeError, ValueError) as exc:
            return f"Workflow 命令未执行: {exc}"
        return "Workflow 命令无效。"

    async def _ensure_binding_for_command(
        self,
        request: WorkflowCommandRequest | EffortCommandRequest,
        *,
        agent: LiveAgentSnapshot,
    ) -> SessionBinding:
        runtime_projection = self._project_runtime(agent=agent, message=request.message)
        dispatch_url, fallback_port = self._dispatch_endpoint_metadata()
        return await self._session_binder.resolve(
            SessionBindingRequest(
                session_key=request.session_key,
                reply_context=build_reply_context(request.message),
                message=request.message,
                gateway_internal_port=fallback_port,
                gateway_dispatch_url=dispatch_url,
                runtime=runtime_projection.runtime,
                profile_version=runtime_projection.profile_version,
            ),
            agent,
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
        prebuilt_projection: _MessagePartsProjection | None,
    ) -> PipelineResult:
        admission_event = asyncio.Event()

        async def _on_cancel(error: GatewayShutdownBeforeSubmit) -> None:
            await self._emit_lifecycle(
                request.routed,
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
                    prebuilt_projection=prebuilt_projection,
                    admission_event=admission_event,
                ),
                on_cancel=_on_cancel,
                admission_event=admission_event,
            )
        except SessionRunQueueSealed:
            await self._emit_lifecycle(
                request.routed,
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
        prebuilt_projection: _MessagePartsProjection | None,
        admission_event: asyncio.Event,
    ) -> PipelineResult:
        run_id: str | None = None
        binding: SessionBinding | None = None
        terminal_followers: tuple[InboundRunRequest, ...] = ()
        active_closed = False
        try:
            failure_kind: str | None = None
            async with self._transition(request.session_key):
                if request.generation != self._session_generations.get(
                    request.session_key, 0
                ):
                    admission_event.set()
                    await self._emit_lifecycle(
                        request.routed,
                        RelayLifecycleUpdate(
                            phase="failed",
                            agent_id=request.agent.agent_id,
                            session_key=request.session_key,
                            error="superseded_by_new_session",
                        ),
                    )
                    return PipelineResult(
                        agent_id=request.agent.agent_id,
                        session_key=request.session_key,
                        kernel_session_id="",
                        run_id="",
                        reply_text="",
                        outbound=None,
                    )
                latest_agent = self._latest_agent(request.agent)
                runtime_projection = self._project_runtime(
                    agent=latest_agent,
                    message=request.message,
                )
                binding = await self._ensure_binding(
                    request,
                    agent=latest_agent,
                    runtime=runtime_projection.runtime,
                    profile_version=runtime_projection.profile_version,
                )
                binding = await self._admit_runtime(
                    binding=binding,
                    agent=latest_agent,
                    routed=request.routed,
                    runtime=runtime_projection.runtime,
                    profile_version=runtime_projection.profile_version,
                )
                if prebuilt_projection is None:
                    projection, failure_kind = await self._build_message_parts(request)
                else:
                    projection = prebuilt_projection
                if failure_kind is None:
                    trace_id = uuid4().hex
                    if self._background_subscriptions is not None:
                        self._background_subscriptions.register_session_event_route(
                            trace_id,
                            binding.reply_context,
                        )
                    # submit() is synchronous. Marker publication is the very next
                    # statement under the same lock: stop/steer cannot see half admission.
                    readable_store = self._readable_input_projection_store
                    if readable_store is not None:
                        readable_store.stage_or_replace(
                            binding.kernel_session_id,
                            projection.model_fallback,
                            projection.readable_fallback,
                        )
                    try:
                        record = self._kernel.submit(
                            session_id=binding.kernel_session_id,
                            parts=projection.model_parts,
                            workspace_root=latest_agent.config.workspace_root,
                            origin=RunOrigin.HUMAN,
                            trace_id=trace_id,
                        )
                    except BaseException:
                        if readable_store is not None:
                            readable_store.rollback(
                                binding.kernel_session_id,
                                projection.model_fallback,
                            )
                        if self._background_subscriptions is not None:
                            self._background_subscriptions.discard_session_event_route(
                                trace_id
                            )
                        raise
                    run_id = record.run_id
                    anchor_sequence = record.start_sequence
                    if run_id:
                        self._active_runs[request.session_key] = _ActiveRunHandle(
                            run_id=run_id,
                            binding=binding,
                            agent=latest_agent,
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
                request.routed,
                RelayLifecycleUpdate(
                    phase="accepted",
                    agent_id=request.agent.agent_id,
                    session_key=request.session_key,
                    run_id=run_id,
                    kernel_session_id=binding.kernel_session_id,
                    model=runtime_projection.runtime.model,
                ),
            )
            (
                run_state,
                reply_text,
                terminal_request,
                recovery_followers,
            ) = await self._await_terminal_run(
                kernel_session_id=binding.kernel_session_id,
                run_id=run_id or "",
                anchor_sequence=anchor_sequence,
                request=request,
                binding=binding,
                model=runtime_projection.runtime.model,
                on_other=lambda event: self._on_other_event(event, binding=binding),
            )
            final_run_id = str(run_state.get("run_id") or run_id or "")
            closed_followers = await self._close_active_run(
                session_key=request.session_key,
                run_id=final_run_id,
            )
            terminal_followers = (*recovery_followers, *closed_followers)
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
                terminal_request.routed,
                RelayLifecycleUpdate(
                    phase="running",
                    agent_id=terminal_request.agent.agent_id,
                    session_key=terminal_request.session_key,
                    run_id=final_run_id,
                    reply_text=reply_text,
                ),
            )
            outbound, detail = await self._deliver_final_reply(
                request=terminal_request,
                binding=binding,
                run_id=final_run_id,
                run_state=run_state,
                reply_text=reply_text,
            )
            result = PipelineResult(
                agent_id=terminal_request.agent.agent_id,
                session_key=terminal_request.session_key,
                kernel_session_id=binding.kernel_session_id,
                run_id=final_run_id,
                reply_text=reply_text,
                outbound=outbound,
            )
            completed = RelayLifecycleUpdate(
                phase="completed",
                agent_id=terminal_request.agent.agent_id,
                session_key=terminal_request.session_key,
                run_id=final_run_id,
                reply_text=reply_text,
                detail=detail,
                usage=self._extract_usage(run_state),
            )
            await self._emit_lifecycle(terminal_request.routed, completed)
            await self._emit_follower_lifecycle(terminal_followers, completed)
            return result
        except asyncio.CancelledError:
            try:
                if run_id:
                    await self._abort_recovery_handoff(
                        predecessor_run_id=run_id,
                        request=request,
                        error=_SHUTDOWN_ACTIVE_RUN_CANCELLED,
                    )
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
                if run_id not in self._terminalized_recovery_roots:
                    await self._emit_lifecycle(request.routed, failed)
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
                if run_id not in self._terminalized_recovery_roots:
                    await self._emit_lifecycle(request.routed, failed)
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
            if run_id:
                self._terminalized_recovery_roots.discard(run_id)

    async def _close_active_run(
        self, *, session_key: str, run_id: str
    ) -> tuple[InboundRunRequest, ...]:
        """Atomically stop steer admission and capture every accepted follower."""

        async with self._transition(session_key):
            return self._close_active_run_locked(
                session_key=session_key,
                run_id=run_id,
            )

    def _close_active_run_locked(
        self, *, session_key: str, run_id: str
    ) -> tuple[InboundRunRequest, ...]:
        """Close an active run while its session transition lock is held."""

        active = self._active_runs.get(session_key)
        if active is not None and active.run_id == run_id:
            self._active_runs.pop(session_key, None)
        self._user_interrupted_runs.discard(run_id)
        self._reset_suppressed_runs.discard(run_id)
        self._consumed_steer_counts.pop(run_id, None)
        return tuple(
            follower.request for follower in self._steered_requests.pop(run_id, ())
        )

    async def _close_failed_successor_without_suffix(
        self, *, session_key: str, run_id: str
    ) -> tuple[InboundRunRequest, ...] | None:
        """Close a failed successor only when no unconsumed follower can re-handoff.

        ``None`` means an admitted suffix exists and recovery retains the logical
        owner. A follower admitted before close is returned for the caller's
        exactly-once failed lifecycle.
        """

        async with self._transition(session_key):
            consumed = self._consumed_steer_counts.get(run_id, 0)
            accepted = self._steered_requests.get(run_id, [])
            if accepted[consumed:]:
                return None
            return self._close_active_run_locked(
                session_key=session_key,
                run_id=run_id,
            )

    async def _emit_follower_lifecycle(
        self,
        followers: tuple[InboundRunRequest, ...],
        update: RelayLifecycleUpdate,
    ) -> None:
        for follower in followers:
            await self._emit_lifecycle(
                follower.routed,
                replace(
                    update,
                    agent_id=follower.agent.agent_id,
                    session_key=follower.session_key,
                ),
            )

    async def _on_other_event(
        self, event: Mapping[str, object], *, binding: SessionBinding
    ) -> None:
        run_id = event.get("run_id")
        if isinstance(run_id, str) and (
            run_id in self._reset_suppressed_runs
            or self._session_binder.is_run_superseded(run_id)
        ):
            return
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
            await asyncio.to_thread(
                self._outbound_router.send_text,
                text=content.strip(),
                reply_context=binding.reply_context,
            )

    async def _deliver_final_reply(
        self,
        *,
        request: InboundRunRequest,
        binding: SessionBinding,
        run_id: str,
        run_state: Mapping[str, object],
        reply_text: str,
    ) -> tuple[OutboundMessage | None, Mapping[str, Any] | None]:
        if (
            run_id in self._reset_suppressed_runs
            or self._session_binder.is_run_superseded(run_id)
        ):
            return None, {"suppressed_by": "superseded_by_new_session"}
        if run_state.get("status") == "cancelled":
            return None, {"suppressed_by": "cancelled"}
        if not reply_text.strip():
            return None, {"suppressed_by": "empty_visible_reply"}
        if self._suppress_reply(reply_text, in_group=request.message.is_group) or (
            _is_external_channel_inbound(request.message)
            and self._is_no_reply_token(reply_text)
        ):
            return None, {"suppressed_by": "no_reply_token"}
        reply_context = binding.reply_context
        external_reply_text = reply_text
        external_runtime_footer = ""
        if _is_external_channel_inbound(request.message):
            if self._external_final_projection_provider is not None:
                cached = self._external_final_projection_provider(run_id)
                if cached:
                    external_reply_text = cached.text
                    external_runtime_footer = cached.runtime_footer
            shadow = request.routed.shadow
            if (
                shadow.saga_id is not None
                and shadow.ref is None
                and self._shadow_output_prepare is not None
            ):
                self._shadow_output_prepare(
                    saga_id=shadow.saga_id,
                    run_id=run_id,
                    output_kind="final",
                    kernel_message_id=None,
                    content=reply_text.strip(),
                )
            metadata = dict(reply_context.metadata)
            metadata.update(
                {
                    "reply_phase": "final",
                    "reply_dedupe_key": f"{run_id}:text:{external_reply_text.strip()}",
                }
            )
            if external_runtime_footer:
                metadata["runtime_footer"] = external_runtime_footer
            feishu_message_id = request.message.metadata.get("feishu_message_id")
            if isinstance(feishu_message_id, str) and feishu_message_id.strip():
                metadata["feishu_message_id"] = feishu_message_id
            reply_context = replace(reply_context, metadata=metadata)
        outbound = await self._outbound_router.send_text_async(
            text=external_reply_text,
            reply_context=reply_context,
        )
        return outbound, None

    async def _build_message_parts(
        self, request: InboundRunRequest
    ) -> tuple[_MessagePartsProjection, str | None]:
        message = request.message
        buffered = (
            self._group_context_store.drain_with_metadata(
                build_group_context_key(message, request.agent.agent_id)
            )
            if message.is_group and self._group_context_store is not None
            else []
        )
        model_parts: list[dict[str, Any]] = []
        readable_parts: list[dict[str, Any]] = []
        projected_messages = [
            *buffered,
            (request.sender_label, message.text, message.metadata),
        ]
        for index, (sender, text, metadata) in enumerate(projected_messages):
            failure = _metadata_image_failure(metadata)
            if failure is not None:
                return _empty_message_parts_projection(), failure
            raw_attachments = metadata.get("attachments")
            image_parts: tuple[dict[str, Any], ...] = ()
            is_current_message = index == len(projected_messages) - 1
            if is_current_message or (
                isinstance(raw_attachments, list) and raw_attachments
            ):
                resolution = await self._image_resolver.resolve(raw_attachments)
                if resolution.failure is not None:
                    return _empty_message_parts_projection(), resolution.failure
                image_parts = resolution.parts
            message_parts = _ordered_kernel_input_parts(
                metadata,
                image_parts=image_parts,
            )
            if message_parts is None:
                message_parts = []
                if text:
                    message_parts.append({"type": "text", "text": text})
                message_parts.extend(image_parts)
            if message.is_group:
                message_parts = _prefix_sender_parts(message_parts, sender=sender)
            readable_parts.extend(dict(part) for part in message_parts)
            frozen = FrozenHumanMessageContext.from_metadata(metadata)
            model_parts.extend(apply_frozen_header(message_parts, frozen))
        return _MessagePartsProjection(
            model_parts=model_parts,
            model_fallback=_render_parts_fallback(model_parts),
            readable_fallback=_render_parts_fallback(readable_parts),
        ), None

    async def _ensure_binding(
        self,
        request: InboundRunRequest,
        *,
        agent: LiveAgentSnapshot,
        runtime: SessionRuntimeConfig,
        profile_version: int | None,
    ) -> SessionBinding:
        """Resolve a stable binding while creating missing sessions with this runtime."""

        dispatch_url, fallback_port = self._dispatch_endpoint_metadata()
        return await self._session_binder.resolve(
            SessionBindingRequest(
                session_key=request.session_key,
                reply_context=_build_routed_reply_context(request.routed),
                message=request.message,
                gateway_internal_port=fallback_port,
                gateway_dispatch_url=dispatch_url,
                runtime=runtime,
                profile_version=profile_version,
            ),
            agent,
        )

    def _latest_agent(self, inbound_agent: LiveAgentSnapshot) -> LiveAgentSnapshot:
        """Read the desired snapshot only after the new-run transition is owned."""

        return self._session_binder.current_agent(inbound_agent.agent_id)

    def _project_runtime(
        self,
        *,
        agent: LiveAgentSnapshot,
        message: InboundMessage,
    ):
        """Produce the sole model-and-capability value for a new run admission."""

        model = self._resolve_agent_model(agent)
        if model is None:
            raise ValueError("new run requires a resolved model")
        return project_agent_runtime(
            agent,
            scenario=dict(message.metadata),
            resolved_model=model,
            reasoning_catalog=self._reasoning_catalog,
            time_context=self._time_context,
        )

    async def _admit_runtime(
        self,
        *,
        binding: SessionBinding,
        agent: LiveAgentSnapshot,
        routed: RoutedInbound,
        runtime: SessionRuntimeConfig,
        profile_version: int | None,
    ) -> SessionBinding:
        """Durably align a retained session before the following synchronous submit."""

        current = await self._kernel.get_session_runtime(
            session_id=binding.kernel_session_id,
            workspace_root=agent.config.workspace_root,
        )
        runtime = self._reconcile_runtime(
            baseline=runtime,
            persisted=current.runtime if current is not None else None,
        )
        desired = self._kernel.identify_runtime(runtime=runtime)
        applied_matches = (
            binding.applied_fingerprint_schema == desired.fingerprint_schema
            and binding.applied_runtime_fingerprint == desired.runtime_fingerprint
        )
        if applied_matches:
            return binding
        replacement_has_known_baseline = current is not None
        if current is not None:
            binding = self._session_binder.persist_applied_runtime(
                binding,
                runtime_fingerprint=current.identity.runtime_fingerprint,
                fingerprint_schema=current.identity.fingerprint_schema,
                profile_version=binding.applied_profile_version,
                agent=agent,
            )
            if (
                current.identity.fingerprint_schema == desired.fingerprint_schema
                and current.identity.runtime_fingerprint == desired.runtime_fingerprint
            ):
                return binding
        result = await self._kernel.reconfigure_session(
            session_id=binding.kernel_session_id,
            workspace_root=agent.config.workspace_root,
            runtime=runtime,
        )
        boundary = (
            self._boundary_for_runtime_replacement(
                routed=routed,
                agent_id=agent.agent_id,
                runtime_fingerprint=result.state.identity.runtime_fingerprint,
                fingerprint_schema=result.state.identity.fingerprint_schema,
                profile_version=profile_version,
            )
            if replacement_has_known_baseline and result.changed
            else None
        )
        if boundary is not None:
            updated = self._session_binder.persist_applied_runtime_with_boundary(
                binding,
                runtime_fingerprint=result.state.identity.runtime_fingerprint,
                fingerprint_schema=result.state.identity.fingerprint_schema,
                profile_version=profile_version,
                boundary=boundary,
                agent=agent,
            )
            if self._boundary_outbox is not None:
                self._boundary_outbox.notify_pending()
            return updated
        pending_boundary = (
            self._pending_boundary_for_shadow_replacement(
                routed=routed,
                agent_id=agent.agent_id,
                runtime_fingerprint=result.state.identity.runtime_fingerprint,
                fingerprint_schema=result.state.identity.fingerprint_schema,
                profile_version=profile_version,
            )
            if replacement_has_known_baseline and result.changed
            else None
        )
        if pending_boundary is not None:
            return self._session_binder.persist_applied_runtime_with_pending_boundary(
                binding,
                runtime_fingerprint=result.state.identity.runtime_fingerprint,
                fingerprint_schema=result.state.identity.fingerprint_schema,
                profile_version=profile_version,
                boundary=pending_boundary,
                agent=agent,
            )
        return self._session_binder.persist_applied_runtime(
            binding,
            runtime_fingerprint=result.state.identity.runtime_fingerprint,
            fingerprint_schema=result.state.identity.fingerprint_schema,
            profile_version=profile_version,
            agent=agent,
        )

    def _reconcile_runtime(
        self,
        *,
        baseline: SessionRuntimeConfig,
        persisted: SessionRuntimeConfig | None,
    ) -> SessionRuntimeConfig:
        """Apply a legal persisted session effort override to a fresh baseline.

        A retained Gateway session must pick up Agent configuration changes each
        admission without losing an override that remains legal for the new model.
        """

        if persisted is None:
            return baseline
        catalog = self._reasoning_catalog
        override = persisted.reasoning_effort_override
        effective_effort = baseline.reasoning_effort
        if override is not None and catalog is not None:
            try:
                effective_effort = catalog.resolve(baseline.model, override)
            except ValueError:
                override = None
        else:
            override = None
        workflow_ultracode = (
            persisted.workflow_ultracode
            and persisted.model == baseline.model
            and override == "xhigh"
            and "Workflow" in baseline.enabled_tools
        )
        return replace(
            baseline,
            reasoning_effort=effective_effort,
            reasoning_effort_override=override,
            workflow_ultracode=workflow_ultracode,
        )

    def _boundary_for_runtime_replacement(
        self,
        *,
        routed: RoutedInbound,
        agent_id: str,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
    ) -> BoundaryIntent | None:
        """Build an outbox intent only when this user message has a durable IM anchor."""

        node_id = self._node_id
        shadow_ref = routed.shadow.ref
        if node_id is None or shadow_ref is None:
            return None
        return BoundaryIntent(
            boundary_id=str(uuid4()),
            node_id=node_id,
            conversation_id=shadow_ref.conversation_id,
            agent_id=agent_id,
            before_message_id=shadow_ref.im_message_id,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
            applied_at=datetime.now(timezone.utc).isoformat(),
        )

    def _pending_boundary_for_shadow_replacement(
        self,
        *,
        routed: RoutedInbound,
        agent_id: str,
        runtime_fingerprint: str,
        fingerprint_schema: str,
        profile_version: int | None,
    ) -> PendingBoundaryIntent | None:
        """Retain an external replacement until its durable saga obtains an IM anchor."""

        node_id = self._node_id
        saga_id = routed.shadow.saga_id
        if node_id is None or saga_id is None:
            return None
        return PendingBoundaryIntent(
            boundary_id=str(uuid4()),
            node_id=node_id,
            agent_id=agent_id,
            runtime_fingerprint=runtime_fingerprint,
            fingerprint_schema=fingerprint_schema,
            profile_version=profile_version,
            applied_at=datetime.now(timezone.utc).isoformat(),
            shadow_saga_id=saga_id,
        )

    async def _ensure_binding_for_stop(self, request: StopRunRequest) -> SessionBinding:
        agent = self._latest_agent(request.agent)
        runtime_projection = self._project_runtime(agent=agent, message=request.message)
        dispatch_url, fallback_port = self._dispatch_endpoint_metadata()
        return await self._session_binder.resolve(
            SessionBindingRequest(
                session_key=request.session_key,
                reply_context=_build_routed_reply_context(request.routed),
                message=request.message,
                gateway_internal_port=fallback_port,
                gateway_dispatch_url=dispatch_url,
                runtime=runtime_projection.runtime,
                profile_version=runtime_projection.profile_version,
            ),
            agent,
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
            source_routed=request.routed,
            operation_id=None,
        )
        await self._emit_lifecycle(
            request.routed,
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
        source_routed: RoutedInbound,
        operation_id: str | None,
    ) -> OutboundMessage | None:
        if (
            operation_id is not None
            and _external_shadow_saga_id(source_routed) is not None
            and self._drain_external_control_deliveries is not None
        ):
            try:
                await self._drain_external_control_deliveries()
            except Exception:  # noqa: BLE001
                logging.getLogger(__name__).exception(
                    "external control delivery deferred for recovery"
                )
            return None
        from_session_id = _control_ack_from_session_id(
            agent_id=agent_id,
            kernel_session_id=binding.kernel_session_id,
            ack_tag=ack_tag,
            source_message=source_routed.message,
            operation_id=operation_id,
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
        return await asyncio.to_thread(
            self._outbound_router.send_text,
            text=text,
            reply_context=binding.reply_context,
        )

    async def _emit_lifecycle(
        self, routed: RoutedInbound, update: RelayLifecycleUpdate
    ) -> None:
        if self._relay_lifecycle_callback is not None:
            await self._relay_lifecycle_callback(routed, update)

    async def _await_terminal_run(
        self,
        *,
        kernel_session_id: str,
        run_id: str,
        anchor_sequence: int | None,
        request: InboundRunRequest,
        binding: SessionBinding,
        model: str,
        on_other: Callable[[Mapping[str, object]], Awaitable[None] | None],
    ) -> tuple[
        Mapping[str, object],
        str,
        InboundRunRequest,
        tuple[InboundRunRequest, ...],
    ]:
        reply_text = ""
        run_state: Mapping[str, object] | None = None
        watchdog_reconciled = False
        stream = self._kernel.stream(
            kernel_session_id, after_sequence=anchor_sequence or 0
        )
        watchdog_timeout: float | None = self._run_idle_timeout_seconds
        next_event_task: asyncio.Task[Mapping[str, object]] | None = None
        try:
            while True:
                try:
                    if next_event_task is None:
                        next_event_task = asyncio.create_task(anext(stream))
                    if watchdog_timeout is None:
                        event = await next_event_task
                    else:
                        done, _ = await asyncio.wait(
                            {next_event_task}, timeout=watchdog_timeout
                        )
                        if not done:
                            if watchdog_reconciled:
                                next_event_task.cancel()
                                await asyncio.gather(
                                    next_event_task, return_exceptions=True
                                )
                                raise TimeoutError(
                                    f"kernel run {run_id} produced no events for "
                                    f"{self._run_idle_timeout_seconds:g}s"
                                )
                            self._kernel.cancel(run_id)
                            await self._emit_terminal_reconcile(
                                run_id, reason="stalled"
                            )
                            watchdog_reconciled = True
                            continue
                        event = next_event_task.result()
                    next_event_task = None
                except StopAsyncIteration:
                    break
                if event.get("run_id") != run_id:
                    result = on_other(event)
                    if asyncio.iscoroutine(result):
                        await result
                    continue
                if event.get("event") == "injection_consumed":
                    consumed_event = self._attach_consumed_steer_identity(run_id, event)
                    if consumed_event is None:
                        continue
                    event = consumed_event
                if self._kernel_event_observer is not None:
                    result = self._kernel_event_observer(event)
                    if asyncio.iscoroutine(result):
                        await result
                event_name = event.get("event")
                if event_name == "permission_request":
                    # Waiting for a human is an intentional parked state, not lost
                    # run liveness. The decision event re-arms the normal watchdog.
                    watchdog_timeout = None
                elif event_name == "permission_resolved":
                    watchdog_timeout = self._run_idle_timeout_seconds
                if event_name == "assistant_message":
                    content = event.get("content")
                    if isinstance(content, str):
                        reply_text = content
                elif (
                    event_name == "run_status"
                    and event.get("status") in TERMINAL_RUN_STATUSES
                ):
                    run_state = event
                    break
            if run_state is None:
                user_stopped = run_id in self._user_interrupted_runs
                if not watchdog_reconciled:
                    await self._emit_terminal_reconcile(run_id, reason="interrupted")
                if user_stopped:
                    return {"status": "cancelled"}, reply_text, request, ()
                raise RuntimeError("stream ended without terminal run_status")
            status = run_state.get("status")
            if status == "completed":
                return run_state, reply_text, request, ()

            user_stopped = run_id in self._user_interrupted_runs
            if not watchdog_reconciled:
                await self._emit_terminal_reconcile(run_id, reason="interrupted")
            if status == "cancelled" and user_stopped:
                return run_state, reply_text, request, ()
            recovery = await self._await_recovery_handoff(
                stream=stream,
                predecessor_run_id=run_id,
                request=request,
                binding=binding,
                model=model,
                on_other=on_other,
            )
            if recovery is not None:
                return recovery
            raise RuntimeError(self._extract_run_error(run_state, str(status or "")))
        finally:
            if next_event_task is not None and not next_event_task.done():
                next_event_task.cancel()
                await asyncio.gather(next_event_task, return_exceptions=True)
            close_stream = getattr(stream, "aclose", None)
            if callable(close_stream):
                await close_stream()

    async def _await_recovery_handoff(
        self,
        *,
        stream: AsyncIterator[Mapping[str, object]],
        predecessor_run_id: str,
        request: InboundRunRequest,
        binding: SessionBinding,
        model: str,
        on_other: Callable[[Mapping[str, object]], Awaitable[None] | None],
        predecessor_terminal_emitted: bool = False,
    ) -> (
        tuple[
            Mapping[str, object],
            str,
            InboundRunRequest,
            tuple[InboundRunRequest, ...],
        ]
        | None
    ):
        """Adopt a validated recovery successor for the unconsumed follower suffix."""

        consumed = self._consumed_steer_counts.get(predecessor_run_id, 0)
        accepted = self._steered_requests.get(predecessor_run_id, [])
        consumed_prefix = tuple(accepted[:consumed])
        suffix = tuple(accepted[consumed:])
        if not suffix:
            return None
        ledger = RecoveryHandoffLedger(
            predecessor_run_id=predecessor_run_id,
            followers=suffix,
        )
        state = _RecoveryHandoffState(
            ledger=ledger,
            claims={},
            completed_run_ids=set(),
            control_event=asyncio.Event(),
        )
        self._recovery_handoffs[predecessor_run_id] = state
        failed = RelayLifecycleUpdate(
            phase="failed",
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            run_id=predecessor_run_id,
            error="predecessor_run_terminal",
        )
        if not predecessor_terminal_emitted:
            await self._emit_lifecycle(request.routed, failed)
        await self._emit_follower_lifecycle(
            tuple(item.request for item in consumed_prefix), failed
        )
        if not predecessor_terminal_emitted:
            self._terminalized_recovery_roots.add(predecessor_run_id)
        async with self._transition(request.session_key):
            self._steered_requests[predecessor_run_id] = list(suffix)
        successor_events: dict[str, list[Mapping[str, object]]] = {}
        try:
            while True:
                event = await self._next_recovery_event(stream=stream, state=state)
                if event is None:
                    return await self._finish_recovery_control(
                        predecessor_run_id=predecessor_run_id,
                        request=request,
                        state=state,
                    )
                if event.get("event") == "recovery_settled":
                    if ledger.observe_settlement(event):
                        break
                    continue
                claim = ledger.observe_successor(event)
                if claim is not None:
                    state.claims[claim.run_id] = claim
                    successor_events.setdefault(claim.run_id, []).append(event)
                    anchor = claim.followers[0].request
                    await self._emit_lifecycle(
                        anchor.routed,
                        RelayLifecycleUpdate(
                            phase="recovery_adopted",
                            agent_id=anchor.agent.agent_id,
                            session_key=anchor.session_key,
                            previous_run_id=predecessor_run_id,
                            run_id=claim.run_id,
                            recovery_id=claim.recovery_id,
                            kernel_session_id=binding.kernel_session_id,
                            model=model,
                        ),
                    )
                    if len(state.claims) == 1:
                        await self._activate_recovery_successor(
                            request=request,
                            binding=binding,
                            claim=claim,
                        )
                    continue
                event_run_id = event.get("run_id")
                if isinstance(event_run_id, str) and event_run_id in state.claims:
                    successor_events.setdefault(event_run_id, []).append(event)
                    continue
                result = on_other(event)
                if asyncio.iscoroutine(result):
                    await result

            if not state.claims:
                raise RecoveryHandoffError("recovery settlement has no user successor")
            async with self._transition(request.session_key):
                self._steered_requests.pop(predecessor_run_id, None)
                self._consumed_steer_counts.pop(predecessor_run_id, None)

            ordered_claims = sorted(
                state.claims.values(), key=lambda item: item.batch_index
            )
            final_result: (
                tuple[
                    Mapping[str, object],
                    str,
                    InboundRunRequest,
                    tuple[InboundRunRequest, ...],
                ]
                | None
            ) = None
            for index, claim in enumerate(ordered_claims):
                await self._activate_recovery_successor(
                    request=request,
                    binding=binding,
                    claim=claim,
                )
                terminal_state, reply_text = await self._await_recovery_successor(
                    stream=stream,
                    state=state,
                    claim=claim,
                    queued=successor_events.get(claim.run_id, []),
                    on_other=on_other,
                )
                if terminal_state is None:
                    return await self._finish_recovery_control(
                        predecessor_run_id=predecessor_run_id,
                        request=request,
                        state=state,
                    )
                anchor = claim.followers[0].request
                if terminal_state.get("status") != "completed":
                    failed = RelayLifecycleUpdate(
                        phase="failed",
                        agent_id=anchor.agent.agent_id,
                        session_key=anchor.session_key,
                        run_id=claim.run_id,
                        error="recovery successor did not complete",
                    )
                    await self._emit_follower_lifecycle(
                        tuple(item.request for item in claim.followers),
                        failed,
                    )
                    self._recovery_handoffs.pop(predecessor_run_id, None)
                    ledger.close()
                    terminal_followers = (
                        await self._close_failed_successor_without_suffix(
                            session_key=request.session_key,
                            run_id=claim.run_id,
                        )
                    )
                    if terminal_followers is not None:
                        # The suffix decision and active-marker close share one
                        # transition lock. A follower admitted before that point is
                        # captured here and must receive a terminal lifecycle.
                        await self._emit_follower_lifecycle(terminal_followers, failed)
                        raise RecoveryHandoffError(
                            "recovery successor did not complete"
                        )
                    nested = await self._await_recovery_handoff(
                        stream=stream,
                        predecessor_run_id=claim.run_id,
                        request=anchor,
                        binding=binding,
                        model=model,
                        on_other=on_other,
                        predecessor_terminal_emitted=True,
                    )
                    if nested is not None:
                        return nested
                    raise RecoveryHandoffError("recovery successor did not complete")
                state.completed_run_ids.add(claim.run_id)
                accepted_during_successor = await self._close_active_run(
                    session_key=request.session_key,
                    run_id=claim.run_id,
                )
                followers = (
                    *(item.request for item in claim.followers[1:]),
                    *accepted_during_successor,
                )
                final_result = terminal_state, reply_text, anchor, followers
                if index < len(ordered_claims) - 1:
                    await self._complete_recovery_batch(
                        request=anchor,
                        followers=followers,
                        binding=binding,
                        run_state=terminal_state,
                        reply_text=reply_text,
                    )
            assert final_result is not None
            self._recovery_handoffs.pop(predecessor_run_id, None)
            ledger.close()
            return final_result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._abort_recovery_handoff(
                predecessor_run_id=predecessor_run_id,
                request=request,
                error=str(exc),
            )
            raise

    async def _next_recovery_event(
        self,
        *,
        stream: AsyncIterator[Mapping[str, object]],
        state: _RecoveryHandoffState,
    ) -> Mapping[str, object] | None:
        """Wait for one protocol event while letting controls fence an idle stream."""

        next_event = asyncio.create_task(anext(stream))
        controlled = asyncio.create_task(state.control_event.wait())
        try:
            done, _ = await asyncio.wait(
                {next_event, controlled},
                timeout=self._run_idle_timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if controlled in done:
                return None
            if next_event in done:
                return next_event.result()
            raise TimeoutError("recovery handoff produced no events")
        finally:
            for task in (next_event, controlled):
                if not task.done():
                    task.cancel()
            await asyncio.gather(next_event, controlled, return_exceptions=True)

    async def _activate_recovery_successor(
        self,
        *,
        request: InboundRunRequest,
        binding: SessionBinding,
        claim: RecoveryHandoffClaim,
    ) -> None:
        """Publish one validated user successor as the logical same-chat owner."""

        anchor = claim.followers[0].request
        async with self._transition(request.session_key):
            self._active_runs[request.session_key] = _ActiveRunHandle(
                run_id=claim.run_id,
                binding=binding,
                agent=anchor.agent,
            )
            self._steered_requests.setdefault(claim.run_id, [])

    async def _await_recovery_successor(
        self,
        *,
        stream: AsyncIterator[Mapping[str, object]],
        state: _RecoveryHandoffState,
        claim: RecoveryHandoffClaim,
        queued: list[Mapping[str, object]],
        on_other: Callable[[Mapping[str, object]], Awaitable[None] | None],
    ) -> tuple[Mapping[str, object] | None, str]:
        """Consume one adopted successor through its terminal status."""

        reply_text = ""
        while True:
            event = (
                queued.pop(0)
                if queued
                else await self._next_recovery_event(stream=stream, state=state)
            )
            if event is None:
                return None, reply_text
            if event.get("run_id") != claim.run_id:
                result = on_other(event)
                if asyncio.iscoroutine(result):
                    await result
                continue
            if event.get("event") == "injection_consumed":
                consumed_event = self._attach_consumed_steer_identity(
                    claim.run_id, event
                )
                if consumed_event is None:
                    continue
                event = consumed_event
            if self._kernel_event_observer is not None:
                result = self._kernel_event_observer(event)
                if asyncio.iscoroutine(result):
                    await result
            if event.get("event") == "assistant_message" and isinstance(
                event.get("content"), str
            ):
                reply_text = str(event["content"])
            if (
                event.get("event") == "run_status"
                and event.get("status") in TERMINAL_RUN_STATUSES
            ):
                return event, reply_text

    async def _complete_recovery_batch(
        self,
        *,
        request: InboundRunRequest,
        followers: tuple[InboundRunRequest, ...],
        binding: SessionBinding,
        run_state: Mapping[str, object],
        reply_text: str,
    ) -> None:
        """Deliver one non-final recovered batch before the logical chain continues."""

        run_id = str(run_state.get("run_id") or "")
        running = RelayLifecycleUpdate(
            phase="running",
            agent_id=request.agent.agent_id,
            session_key=request.session_key,
            run_id=run_id,
            reply_text=reply_text,
        )
        await self._emit_lifecycle(request.routed, running)
        _, detail = await self._deliver_final_reply(
            request=request,
            binding=binding,
            run_id=run_id,
            run_state=run_state,
            reply_text=reply_text,
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
        await self._emit_lifecycle(request.routed, completed)
        await self._emit_follower_lifecycle(followers, completed)

    def _fence_recovery_for_control(self, run_id: str, *, reset: bool) -> None:
        """Wake and fence a recovery ledger reached by an explicit control."""

        for predecessor_run_id, state in self._recovery_handoffs.items():
            successor_run_ids = state.ledger.successor_run_ids
            if run_id != predecessor_run_id and run_id not in successor_run_ids:
                continue
            affected = (predecessor_run_id, *successor_run_ids)
            markers = (
                self._reset_suppressed_runs if reset else self._user_interrupted_runs
            )
            markers.update(affected)
            state.ledger.close()
            state.control_event.set()
            for successor_run_id in successor_run_ids:
                if successor_run_id not in state.completed_run_ids:
                    self._kernel.cancel(successor_run_id)
            return

    async def _finish_recovery_control(
        self,
        *,
        predecessor_run_id: str,
        request: InboundRunRequest,
        state: _RecoveryHandoffState,
    ) -> tuple[
        Mapping[str, object],
        str,
        InboundRunRequest,
        tuple[InboundRunRequest, ...],
    ]:
        """Close an adopted chain under `/stop` or `/new` without visible output."""

        ordered = sorted(state.claims.values(), key=lambda item: item.batch_index)
        if not ordered:
            await self._abort_recovery_handoff(
                predecessor_run_id=predecessor_run_id,
                request=request,
                error="recovery interrupted by control",
            )
            raise RecoveryHandoffError("recovery interrupted by control")
        anchor = ordered[0].followers[0].request
        claimed = tuple(
            follower.request
            for claim in ordered
            for follower in claim.followers
            if follower.request is not anchor
        )
        claimed_pending_ids = {
            follower.pending_id for claim in ordered for follower in claim.followers
        }
        unclaimed = tuple(
            item.request
            for item in self._steered_requests.get(predecessor_run_id, ())
            if item.pending_id not in claimed_pending_ids
        )
        followers = claimed + unclaimed
        for successor_run_id in state.ledger.successor_run_ids:
            followers += tuple(
                item.request
                for item in self._steered_requests.pop(successor_run_id, ())
            )
        async with self._transition(request.session_key):
            self._recovery_handoffs.pop(predecessor_run_id, None)
            self._steered_requests.pop(predecessor_run_id, None)
            self._consumed_steer_counts.pop(predecessor_run_id, None)
        return (
            {
                "event": "run_status",
                "run_id": ordered[0].run_id,
                "status": "cancelled",
            },
            "",
            anchor,
            followers,
        )

    async def _abort_recovery_handoff(
        self,
        *,
        predecessor_run_id: str,
        request: InboundRunRequest,
        error: str,
    ) -> None:
        """Fail every unsettled accepted follower and fence known successors."""

        state = self._recovery_handoffs.pop(predecessor_run_id, None)
        if state is None:
            return
        for successor_run_id in state.ledger.successor_run_ids:
            if successor_run_id not in state.completed_run_ids:
                self._kernel.cancel(successor_run_id)
        state.ledger.close()
        claimed_pending_ids: set[str] = set()
        for claim in state.claims.values():
            claimed_pending_ids.update(item.pending_id for item in claim.followers)
            failed = RelayLifecycleUpdate(
                phase="failed",
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                run_id=claim.run_id,
                error=error,
            )
            await self._emit_follower_lifecycle(
                tuple(item.request for item in claim.followers), failed
            )
            accepted_during_successor = tuple(
                item.request for item in self._steered_requests.pop(claim.run_id, ())
            )
            await self._emit_follower_lifecycle(accepted_during_successor, failed)
        unclaimed = tuple(
            item.request
            for item in self._steered_requests.pop(predecessor_run_id, ())
            if item.pending_id not in claimed_pending_ids
        )
        await self._emit_follower_lifecycle(
            unclaimed,
            RelayLifecycleUpdate(
                phase="failed",
                agent_id=request.agent.agent_id,
                session_key=request.session_key,
                run_id=predecessor_run_id,
                error=error,
            ),
        )
        async with self._transition(request.session_key):
            active = self._active_runs.get(request.session_key)
            if active is not None and (
                active.run_id == predecessor_run_id
                or active.run_id in state.ledger.successor_run_ids
            ):
                self._active_runs.pop(request.session_key, None)

    def _attach_consumed_steer_identity(
        self, run_id: str, event: Mapping[str, object]
    ) -> Mapping[str, object] | None:
        raw_user_count = event.get("user_message_count")
        raw_background_returns = event.get("background_returns")
        if (
            raw_user_count == 0
            and isinstance(raw_background_returns, list)
            and raw_background_returns
        ):
            # Background task notifications share the pending-message queue, but
            # they are not user steers and have no follower identity to attach.
            # Their sidecars still have to cross the delivery observer so the
            # model's reply and raw task return land on the same IM message.
            return event
        raw_count = (
            raw_user_count
            if isinstance(raw_user_count, int)
            else event.get("message_count")
        )
        message_count = (
            raw_count
            if isinstance(raw_count, int)
            and not isinstance(raw_count, bool)
            and raw_count >= 0
            else 1
        )
        if message_count == 0:
            return None
        followers = self._steered_requests.get(run_id, [])
        index = self._consumed_steer_counts.get(run_id, 0)
        if index >= len(followers):
            return event
        end = min(index + message_count, len(followers))
        self._consumed_steer_counts[run_id] = end
        shadow = followers[end - 1].request.routed.shadow
        enriched = dict(event)
        if shadow.saga_id is not None:
            enriched["shadow_saga_id"] = shadow.saga_id
            enriched["shadow_anchor_pending"] = shadow.ref is None
        if shadow.ref is not None:
            enriched["shadow_conversation_id"] = shadow.ref.conversation_id
        return enriched

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
        configured_default = self._product_default_model
        if configured_default is None:
            get_llm_config = getattr(self._kernel, "get_llm_config", None)
            if callable(get_llm_config):
                config = get_llm_config()
                configured_default = config.default_model or config.model
        return resolve_run_model(agent.config, product_default=configured_default)

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


def _metadata_image_failure(metadata: Mapping[str, Any]) -> str | None:
    failure = metadata.get("image_resolution_failure")
    return failure if failure in _IMAGE_FAILURE_MESSAGES else None


def _empty_message_parts_projection() -> _MessagePartsProjection:
    return _MessagePartsProjection(
        model_parts=[], model_fallback="", readable_fallback=""
    )


def _render_parts_fallback(parts: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for part in parts:
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            lines.append(part["text"])
        elif part.get("type") == "image":
            lines.append("[image:placeholder]")
    return "\n".join(lines)


def _ordered_kernel_input_parts(
    metadata: Mapping[str, Any],
    *,
    image_parts: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]] | None:
    raw_parts = metadata.get("kernel_input_parts")
    if not isinstance(raw_parts, list):
        return None
    parts: list[dict[str, Any]] = []
    for item in raw_parts:
        if not isinstance(item, Mapping):
            continue
        part_type = item.get("type")
        if part_type == "text":
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append({"type": "text", "text": text})
            continue
        if part_type != "image":
            continue
        attachment_index = item.get("attachment_index")
        if (
            isinstance(attachment_index, int)
            and not isinstance(attachment_index, bool)
            and 0 <= attachment_index < len(image_parts)
        ):
            parts.append(dict(image_parts[attachment_index]))
    return parts


def _prefix_sender_parts(
    parts: list[dict[str, Any]],
    *,
    sender: str,
) -> list[dict[str, Any]]:
    normalized = sender.strip()
    if not normalized:
        return parts
    prefixed = [dict(part) for part in parts]
    if prefixed and prefixed[0].get("type") == "text":
        text = prefixed[0].get("text")
        if isinstance(text, str):
            prefixed[0]["text"] = f"[{normalized}] {text}"
            return prefixed
    prefixed.insert(0, {"type": "text", "text": f"[{normalized}]"})
    return prefixed


def _control_ack_from_session_id(
    *,
    agent_id: str,
    kernel_session_id: str,
    ack_tag: str,
    source_message: InboundMessage,
    operation_id: str | None,
) -> str:
    """Build the stable IM dispatch key for one visible control acknowledgement."""

    if operation_id:
        return (
            f"{agent_id}|tool_call:control:{ack_tag}:"
            f"{_normalize_dispatch_id_part(operation_id)}"
        )
    base = f"{agent_id}|tool_call:{kernel_session_id}:{ack_tag}"
    source_id = _control_ack_source_id(source_message)
    if source_id is None:
        return base
    return f"{base}:{source_id}"


def _control_ack_source_id(message: InboundMessage) -> str | None:
    relay = message.ingress.im_relay
    if relay is not None:
        value = relay.im_message_id or relay.relay_task_id or relay.idempotency_key
        return _normalize_dispatch_id_part(value)
    external_event = message.ingress.external_event
    if external_event is not None:
        return _normalize_dispatch_id_part(external_event.provider_event_id)
    return None


def _external_shadow_saga_id(routed: RoutedInbound) -> str | None:
    """Return the durable external saga identity when this command owns one."""

    external_identity = routed.message.ingress.external_conversation
    if external_identity is None:
        return None
    if external_identity.trigger_source == "im":
        return None
    return routed.shadow.saga_id


def _named_workflow_instruction(command: WorkflowCommand) -> str:
    """Expand a discovered named command into an explicit normal model turn."""

    instruction = (
        f'Run the saved Workflow named "{command.name}" using the Workflow tool '
        "name input. Do not replace it with an inline script."
    )
    if command.arguments:
        instruction += f" User arguments: {command.arguments}"
    return instruction


def _normalize_dispatch_id_part(value: str) -> str:
    normalized = "_".join(value.strip().split()).replace("|", "_")
    return normalized[:160] if len(normalized) > 160 else normalized


def _is_external_channel_inbound(message: InboundMessage) -> bool:
    """Return whether normalized protocol facts identify an external ingress."""

    external_identity = message.ingress.external_conversation
    return external_identity is not None and external_identity.trigger_source != "im"
