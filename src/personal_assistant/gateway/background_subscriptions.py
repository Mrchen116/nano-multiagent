"""Own background event subscribers for all live Gateway sessions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
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
    from agent.sdk.kernel import Kernel


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


class BackgroundSubscriptionManager:
    """Ensure one subscriber per Kernel session and own its shutdown lifecycle.

    Args:
        kernel: In-process Kernel whose session event stream is subscribed.
        session_event_callback: Optional receiver for session-level events.
        bg_reply_sender: Optional visible text sender for BACKGROUND_TASK output.
    """

    def __init__(
        self,
        *,
        kernel: "Kernel",
        session_event_callback: Callable[
            [str, Mapping[str, Any]], Awaitable[None]
        ]
        | None = None,
        bg_reply_sender: Callable[
            [str, ReplyContext, str], Awaitable[None]
        ]
        | None = None,
    ) -> None:
        self._kernel = kernel
        self._session_event_callback = session_event_callback
        self._bg_reply_sender = bg_reply_sender
        self._subscribers: dict[str, BackgroundSessionEventSubscriber] = {}
        self._lock = asyncio.Lock()
        self._sealed = False

    async def ensure(self, request: BackgroundSubscriptionRequest) -> None:
        """Start a subscriber once and preserve its original replay/routing context.

        Args:
            request: Session, replay anchor, reply target and explicit Agent identity.

        Raises:
            RuntimeError: When new subscription admission has been sealed.
        """

        if self._sealed:
            raise RuntimeError("background subscription manager is sealed")
        if (
            self._session_event_callback is None
            and (request.reply_context is None or self._bg_reply_sender is None)
        ):
            return
        async with self._lock:
            if self._sealed:
                raise RuntimeError("background subscription manager is sealed")
            if request.session_id in self._subscribers:
                return
            subscriber = self._build_subscriber(request)
            self._subscribers[request.session_id] = subscriber
            try:
                await subscriber.start()
            except BaseException:
                self._subscribers.pop(request.session_id, None)
                raise

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
            return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self._subscribers.clear()
        timed_out = [
            session_id
            for (session_id, _), result in zip(subscribers, results, strict=True)
            if isinstance(result, TimeoutError)
        ]
        other_errors = [
            result
            for result in results
            if isinstance(result, BaseException) and not isinstance(result, TimeoutError)
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
            if session_event_callback is not None:
                await session_event_callback(request.session_id, event)

        bg_run_output_callback = None
        if request.reply_context is not None and self._bg_reply_sender is not None:
            reply_context = request.reply_context
            sender = self._bg_reply_sender

            async def _relay_bg_run_output(event: Mapping[str, Any]) -> None:
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

        return BackgroundSessionEventSubscriber(
            kernel_client=_KernelStreamAdapter(self._kernel, request.session_id),
            session_id=request.session_id,
            on_event=_on_session_event,
            after_sequence=request.after_sequence,
            bg_run_output_callback=bg_run_output_callback,
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
