"""Own background event subscribers for all live Gateway sessions."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from personal_assistant.channels.base import ReplyContext
from personal_assistant.gateway.background_session_events import (
    BackgroundSessionEventSubscriber,
)
from personal_assistant.gateway.reply_visibility import (
    ReplyVisibilityPolicy,
    should_suppress_reply,
)

if TYPE_CHECKING:
    from agent.sdk import Kernel


_MAX_SESSION_EVENT_ROUTES = 4096


@dataclass(frozen=True, slots=True)
class BackgroundSubscriptionRequest:
    """Describe one per-session background subscription.

    Args:
        session_id: Kernel session whose events continue after the main turn.
        after_sequence: Last sequence consumed by the main turn.
        reply_context: Original channel target for background visible output.
        agent_id: Explicit source Agent identity used in the IM deduplication key.
    """

    session_id: str
    after_sequence: int
    reply_context: ReplyContext | None
    agent_id: str


class ForegroundTerminalSubscriptionOutcome(StrEnum):
    """Describe optional background admission after a foreground terminal."""

    STARTED = "started"
    ALREADY_ACTIVE = "already_active"
    NOT_REQUIRED = "not_required"
    SHUTDOWN_SKIPPED = "shutdown_skipped"


class BackgroundSubscriptionManager:
    """Ensure one subscriber per Kernel session and own its shutdown lifecycle.

    Args:
        kernel: In-process Kernel whose session event stream is subscribed.
        session_event_callback: Optional receiver for session-level events.
        bg_reply_sender: Optional visible text sender for BACKGROUND_TASK output.
        skill_created_handler: Optional synchronous config-sync handler for
            source-marked self-evolution skill creation.
    """

    def __init__(
        self,
        *,
        kernel: "Kernel",
        session_event_callback: Callable[
            [ReplyContext, str, str, Mapping[str, Any]], Awaitable[None]
        ]
        | None = None,
        bg_reply_sender: Callable[[str, ReplyContext, str], Awaitable[None]]
        | None = None,
        skill_created_handler: Callable[[str, Mapping[str, object]], object]
        | None = None,
    ) -> None:
        self._kernel = kernel
        self._session_event_callback = session_event_callback
        self._bg_reply_sender = bg_reply_sender
        self._skill_created_handler = skill_created_handler
        self._subscribers: dict[str, BackgroundSessionEventSubscriber] = {}
        self._background_reply_contexts: dict[str, ReplyContext] = {}
        self._session_event_routes: OrderedDict[str, ReplyContext] = OrderedDict()
        self._lock = asyncio.Lock()
        self._sealed = False

    def register_session_event_route(
        self, trace_id: str, reply_context: ReplyContext
    ) -> None:
        """Freeze one run's reply route until its session notice arrives.

        Args:
            trace_id: Opaque Kernel run correlation identity.
            reply_context: Immutable trigger-source route for that run.
        """

        self._session_event_routes[trace_id] = ReplyContext(
            channel_name=reply_context.channel_name,
            target_chat_id=reply_context.target_chat_id,
            thread_id=reply_context.thread_id,
            metadata=dict(reply_context.metadata),
        )
        self._session_event_routes.move_to_end(trace_id)
        while len(self._session_event_routes) > _MAX_SESSION_EVENT_ROUTES:
            self._session_event_routes.popitem(last=False)

    def discard_session_event_route(self, trace_id: str) -> None:
        """Discard a route whose Kernel submit did not succeed."""

        self._session_event_routes.pop(trace_id, None)

    async def ensure(self, request: BackgroundSubscriptionRequest) -> None:
        """Start a subscriber once and preserve its original replay/routing context.

        Args:
            request: Session, replay anchor, reply target and explicit Agent identity.

        Raises:
            RuntimeError: When new subscription admission has been sealed.
        """

        async with self._lock:
            if request.session_id in self._subscribers:
                self._adopt_background_reply_route(request)
                return
            if self._sealed:
                raise RuntimeError("background subscription manager is sealed")
            await self._start_locked(request)

    async def ensure_after_foreground_terminal(
        self, request: BackgroundSubscriptionRequest
    ) -> ForegroundTerminalSubscriptionOutcome:
        """Optionally subscribe without making foreground success depend on shutdown.

        The foreground run has already reached a Kernel terminal before this method
        is called. A concurrent Gateway seal therefore means no new background work
        may be admitted, not that the completed foreground run failed.

        Args:
            request: Session, replay anchor, reply target and explicit Agent identity.

        Returns:
            Typed admission outcome; shutdown rejection is a normal result.
        """

        async with self._lock:
            if request.session_id in self._subscribers:
                self._adopt_background_reply_route(request)
                return ForegroundTerminalSubscriptionOutcome.ALREADY_ACTIVE
            if self._sealed:
                return ForegroundTerminalSubscriptionOutcome.SHUTDOWN_SKIPPED
            if await self._start_locked(request):
                return ForegroundTerminalSubscriptionOutcome.STARTED
            return ForegroundTerminalSubscriptionOutcome.NOT_REQUIRED

    def seal(self) -> None:
        """Synchronously reject new subscribers without cancelling existing ones."""

        self._sealed = True

    async def aclose(self, deadline: float) -> None:
        """Stop all existing subscribers concurrently by one absolute deadline.

        Args:
            deadline: Absolute monotonic deadline from the owning Gateway event loop.

        Raises:
            TimeoutError: When one or more subscribers require deadline cancellation.
        """

        self.seal()
        subscribers = tuple(self._subscribers.items())
        for _, subscriber in subscribers:
            subscriber.request_stop()
        tasks = [
            asyncio.create_task(
                subscriber.aclose(deadline),
                name=f"bg-sub-close:{session_id}",
            )
            for session_id, subscriber in subscribers
        ]
        if not tasks:
            self._background_reply_contexts.clear()
            self._session_event_routes.clear()
            return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self._subscribers.clear()
        self._background_reply_contexts.clear()
        self._session_event_routes.clear()
        timed_out = [
            session_id
            for (session_id, _), result in zip(subscribers, results, strict=True)
            if isinstance(result, TimeoutError)
        ]
        other_errors = [
            result
            for result in results
            if isinstance(result, BaseException)
            and not isinstance(result, TimeoutError)
        ]
        if other_errors:
            raise ExceptionGroup("background subscriber close failed", other_errors)
        if timed_out:
            raise TimeoutError(
                f"background subscribers exceeded deadline: {sorted(timed_out)}"
            )

    def _build_subscriber(
        self, request: BackgroundSubscriptionRequest
    ) -> BackgroundSessionEventSubscriber:
        session_event_callback = self._session_event_callback

        async def _on_session_event(event: Mapping[str, Any]) -> None:
            if session_event_callback is None:
                return
            trace_id = event.get("originating_trace_id")
            if not isinstance(trace_id, str) or not trace_id:
                return
            reply_context = self._session_event_routes.pop(trace_id, None)
            if reply_context is None:
                return
            await session_event_callback(
                reply_context,
                request.agent_id,
                request.session_id,
                event,
            )

        bg_run_output_callback = None
        if self._bg_reply_sender is not None:
            sender = self._bg_reply_sender

            async def _relay_bg_run_output(event: Mapping[str, Any]) -> None:
                reply_context = self._background_reply_contexts.get(request.session_id)
                if reply_context is None:
                    return
                content = event.get("content")
                if not isinstance(content, str) or not content.strip():
                    return
                text = content.strip()
                if should_suppress_reply(
                    text,
                    policy=ReplyVisibilityPolicy.SUPPRESS_PROTOCOL_TOKENS,
                ):
                    return
                sequence = event.get("_id") or event.get("sequence_num")
                dedupe = (
                    f"{request.session_id}:{sequence}"
                    if sequence is not None
                    else request.session_id
                )
                await sender(
                    text,
                    reply_context,
                    f"{request.agent_id}|tool_call:{dedupe}",
                )

            bg_run_output_callback = _relay_bg_run_output

        skill_created_callback = None
        if self._skill_created_handler is not None:
            handler = self._skill_created_handler

            async def _sync_self_evolution_skill(event: Mapping[str, Any]) -> None:
                await asyncio.to_thread(handler, request.agent_id, event)

            skill_created_callback = _sync_self_evolution_skill

        return BackgroundSessionEventSubscriber(
            kernel_client=_KernelStreamAdapter(self._kernel, request.session_id),
            session_id=request.session_id,
            on_event=_on_session_event,
            after_sequence=request.after_sequence,
            bg_run_output_callback=bg_run_output_callback,
            skill_created_callback=skill_created_callback,
        )

    async def _start_locked(self, request: BackgroundSubscriptionRequest) -> bool:
        """Start one subscriber while the manager admission lock is held."""

        has_session_delivery = self._session_event_callback is not None
        has_background_delivery = (
            request.reply_context is not None and self._bg_reply_sender is not None
        )
        has_skill_sync = self._skill_created_handler is not None
        if (
            not has_session_delivery
            and not has_background_delivery
            and not has_skill_sync
        ):
            return False
        self._adopt_background_reply_route(request)
        subscriber = self._build_subscriber(request)
        self._subscribers[request.session_id] = subscriber
        try:
            await subscriber.start()
        except BaseException:
            self._subscribers.pop(request.session_id, None)
            raise
        return True

    def _adopt_background_reply_route(
        self, request: BackgroundSubscriptionRequest
    ) -> None:
        """Freeze the first usable ordinary-background route for one session."""

        if (
            request.reply_context is None
            or request.session_id in self._background_reply_contexts
        ):
            return
        reply_context = request.reply_context
        self._background_reply_contexts[request.session_id] = ReplyContext(
            channel_name=reply_context.channel_name,
            target_chat_id=reply_context.target_chat_id,
            thread_id=reply_context.thread_id,
            metadata=dict(reply_context.metadata),
        )


class _KernelStreamAdapter:
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
        del workspace_root
        async for event in self._kernel.stream(
            session_id or self._session_id,
            after_sequence=last_event_id or 0,
        ):
            yield event
