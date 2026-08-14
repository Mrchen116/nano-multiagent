"""Route outbound replies back through the originating channel adapter."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Mapping
from concurrent.futures import Future
from threading import Lock

from personal_assistant.channels.base import OutboundMessage, ReplyContext
from personal_assistant.gateway.channel_registry import ChannelRegistry

_MAX_DEDUPE_KEYS = 4096


class OutboundRouter:
    """Send normalized replies to the adapter captured in reply context."""

    def __init__(
        self, registry: ChannelRegistry, *, max_dedupe_keys: int = _MAX_DEDUPE_KEYS
    ) -> None:
        self._registry = registry
        self._sent_dedupe_keys: OrderedDict[str, None] = OrderedDict()
        self._active_dedupe_flights: dict[str, Future[bool]] = {}
        self._dedupe_lock = Lock()
        self._max_dedupe_keys = max(1, max_dedupe_keys)

    def send_text(
        self, *, text: str, reply_context: ReplyContext
    ) -> OutboundMessage | None:
        """Build and dispatch one outbound text reply.

        Args:
            text: Reply text produced by the kernel execution.
            reply_context: Original target captured from the inbound message.

        Returns:
            The normalized outbound payload sent to the adapter, or ``None`` when
            ``reply_dedupe_key`` identifies a reply already delivered through this
            router.

        Raises:
            LookupError: When the target channel adapter is not registered.

        Notes:
            Dedupe keys are reserved atomically before provider I/O. A competing
            synchronous send is suppressed while an owner is active. Async callers
            use :meth:`send_text_async` when failure must transfer the retry.
        """

        channel = self._registry.get(reply_context.channel_name)
        if channel is None:
            raise LookupError(f"unknown channel adapter: {reply_context.channel_name}")
        dedupe_keys = self._dedupe_keys_for(text=text, metadata=reply_context.metadata)
        is_owner, outcome = self._claim_dedupe_keys(dedupe_keys)
        if not is_owner:
            return None
        outbound = OutboundMessage(
            channel_name=reply_context.channel_name,
            text=text,
            target_chat_id=reply_context.target_chat_id,
            thread_id=reply_context.thread_id,
            metadata=dict(reply_context.metadata),
        )
        try:
            channel.send(outbound)
        except Exception:
            self._finish_dedupe_flight(dedupe_keys, outcome, delivered=False)
            raise
        self._finish_dedupe_flight(dedupe_keys, outcome, delivered=True)
        return outbound

    async def send_text_async(
        self, *, text: str, reply_context: ReplyContext
    ) -> OutboundMessage | None:
        """Dispatch text without blocking the event loop or cancellation on a waiter.

        Args:
            text: Reply text produced by the kernel execution.
            reply_context: Original target captured from the inbound message.

        Returns:
            The normalized payload sent by this call, or ``None`` when an overlapping
            or completed delivery already owns the reply.

        Raises:
            LookupError: When the target channel adapter is not registered.

        Notes:
            Overlapping callers await the active owner's explicit provider outcome.
            Owner success suppresses the waiter even if completed keys are immediately
            evicted; owner failure lets a still-live waiter claim and retry.
        """

        channel = self._registry.get(reply_context.channel_name)
        if channel is None:
            raise LookupError(f"unknown channel adapter: {reply_context.channel_name}")
        dedupe_keys = self._dedupe_keys_for(text=text, metadata=reply_context.metadata)
        while True:
            is_owner, outcome = self._claim_dedupe_keys(dedupe_keys)
            if is_owner:
                break
            if outcome is None or await asyncio.shield(asyncio.wrap_future(outcome)):
                return None

        outbound = OutboundMessage(
            channel_name=reply_context.channel_name,
            text=text,
            target_chat_id=reply_context.target_chat_id,
            thread_id=reply_context.thread_id,
            metadata=dict(reply_context.metadata),
        )
        send_task = asyncio.create_task(asyncio.to_thread(channel.send, outbound))
        try:
            await asyncio.shield(send_task)
        except asyncio.CancelledError:
            send_task.add_done_callback(
                lambda completed: self._finish_cancelled_owner(
                    dedupe_keys, outcome, completed
                )
            )
            raise
        except Exception:
            self._finish_dedupe_flight(dedupe_keys, outcome, delivered=False)
            raise
        self._finish_dedupe_flight(dedupe_keys, outcome, delivered=True)
        return outbound

    def _claim_dedupe_keys(
        self, dedupe_keys: set[str]
    ) -> tuple[bool, Future[bool] | None]:
        """Claim every key or return the overlapping owner's explicit outcome."""

        if not dedupe_keys:
            return True, None
        with self._dedupe_lock:
            if any(key in self._sent_dedupe_keys for key in dedupe_keys):
                return False, None
            for key in dedupe_keys:
                active_outcome = self._active_dedupe_flights.get(key)
                if active_outcome is not None:
                    return False, active_outcome
            outcome: Future[bool] = Future()
            for key in dedupe_keys:
                self._active_dedupe_flights[key] = outcome
            return True, outcome

    def _finish_dedupe_flight(
        self,
        dedupe_keys: set[str],
        outcome: Future[bool] | None,
        *,
        delivered: bool,
    ) -> None:
        if outcome is None:
            return
        with self._dedupe_lock:
            if delivered:
                for key in dedupe_keys:
                    self._sent_dedupe_keys[key] = None
                    self._sent_dedupe_keys.move_to_end(key)
                while len(self._sent_dedupe_keys) > self._max_dedupe_keys:
                    self._sent_dedupe_keys.popitem(last=False)
            for key in dedupe_keys:
                if self._active_dedupe_flights.get(key) is outcome:
                    del self._active_dedupe_flights[key]
            outcome.set_result(delivered)

    def _finish_cancelled_owner(
        self,
        dedupe_keys: set[str],
        outcome: Future[bool] | None,
        send_task: asyncio.Task[None],
    ) -> None:
        delivered = not send_task.cancelled() and send_task.exception() is None
        self._finish_dedupe_flight(dedupe_keys, outcome, delivered=delivered)

    @staticmethod
    def _dedupe_keys_for(*, text: str, metadata: object) -> set[str]:
        """Return physical and semantic dedupe keys for one outbound send."""

        if not isinstance(metadata, Mapping):
            return set()
        keys: set[str] = set()
        dedupe_key = metadata.get("reply_dedupe_key")
        if isinstance(dedupe_key, str) and dedupe_key.strip():
            normalized_key = dedupe_key.strip()
            keys.add(normalized_key)
            if metadata.get("reply_phase") == "final":
                run_id, _, _ = normalized_key.partition(":")
                cleaned_text = text.strip()
                if run_id and cleaned_text:
                    keys.add(f"{run_id}:final_text:{cleaned_text}")
        return keys
