"""Per-session FIFO execution queues for Gateway inbound runs."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SessionRunQueueSealed(RuntimeError):
    """Report that Gateway shutdown has closed queue admission."""


class GatewayShutdownBeforeSubmit(RuntimeError):
    """Give accepted FIFO work an explicit pre-Kernel shutdown outcome."""

    reason = "gateway_shutdown_before_submit"

    def __init__(self) -> None:
        super().__init__(self.reason)


@dataclass(slots=True)
class _QueueItem(Generic[T]):
    session_key: str
    item_id: str
    future: asyncio.Future[T]
    operation: Callable[[], Awaitable[T]]
    on_cancel: Callable[[GatewayShutdownBeforeSubmit], Awaitable[None]] | None
    admission_event: asyncio.Event
    queue_owns_admission_event: bool


class SessionRunQueue:
    """Serialize work per session and own every queue worker through shutdown.

    Notes:
        ``seal_and_cancel_pending`` is an O(1) synchronous admission switch: it only
        rejects later submissions. ``settle_admission`` owns the per-item async phase
        that removes queued work while preserving an executing head. Removed items
        receive ``gateway_shutdown_before_submit`` without reaching their operation,
        and cancellation callbacks remain owned through the shared deadline.
    """

    def __init__(self) -> None:
        self._queues: dict[str, deque[_QueueItem[Any]]] = {}
        self._active_sessions: set[str] = set()
        self._running_sessions: set[str] = set()
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._settlement_tasks: set[asyncio.Task[None]] = set()
        self._sealed = False
        self._item_sequence = 0

    async def submit(
        self,
        session_key: str,
        operation: Callable[[], Awaitable[T]],
        *,
        on_cancel: Callable[[GatewayShutdownBeforeSubmit], Awaitable[None]]
        | None = None,
        admission_event: asyncio.Event | None = None,
    ) -> T:
        """Queue one operation under a session serialization key.

        Args:
            session_key: Gateway-local session key controlling FIFO scope.
            operation: Coroutine factory executed when the item reaches the head.
            on_cancel: Optional lifecycle callback for shutdown-before-submit.
            admission_event: Optional event set by the operation after submit-or-rollback.
                Without one, the queue considers admission settled when operation begins.

        Returns:
            The operation result.

        Raises:
            SessionRunQueueSealed: When called after queue admission is sealed.
            GatewayShutdownBeforeSubmit: When accepted work is cancelled before execution.
        """

        if self._sealed:
            raise SessionRunQueueSealed("session run queue is sealed")
        loop = asyncio.get_running_loop()
        self._item_sequence += 1
        future: asyncio.Future[T] = loop.create_future()
        owns_admission_event = admission_event is None
        item = _QueueItem(
            session_key=session_key,
            item_id=f"item-{self._item_sequence}",
            future=future,
            operation=operation,
            on_cancel=on_cancel,
            admission_event=admission_event or asyncio.Event(),
            queue_owns_admission_event=owns_admission_event,
        )
        queue = self._queues.setdefault(session_key, deque())
        queue.append(item)
        if session_key not in self._active_sessions:
            self._active_sessions.add(session_key)
            worker = loop.create_task(
                self._drain_session(session_key),
                name=f"session-run-queue:{session_key}",
            )
            self._workers[session_key] = worker
            worker.add_done_callback(
                lambda done, key=session_key: self._worker_done(key, done)
            )
        return await future

    def is_active(self, session_key: str) -> bool:
        """Return whether the session owns or awaits queue execution."""

        return session_key in self._active_sessions

    def seal_and_cancel_pending(self) -> None:
        """Synchronously reject new work without walking accepted queue items."""

        self._sealed = True

    async def settle_admission(self, deadline: float) -> None:
        """Wait for every accepted item to cross submit-or-rollback by one deadline."""

        if self._sealed:
            self._cancel_pending_items()
        event_waiters = [
            asyncio.create_task(
                item.admission_event.wait(),
                name=(
                    "session-run-admission:"
                    f"session_key={item.session_key}:item_id={item.item_id}"
                ),
            )
            for queue in self._queues.values()
            for item in queue
            if not item.admission_event.is_set()
        ]
        settlement = list(self._settlement_tasks)
        waiters: list[asyncio.Future[Any] | asyncio.Task[Any]] = [
            *event_waiters,
            *settlement,
        ]
        if not waiters:
            return
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        _, pending = await asyncio.wait(waiters, timeout=remaining)
        if not pending:
            return
        pending_names = sorted(item.get_name() for item in pending)
        for pending_item in pending:
            pending_item.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise TimeoutError(
            "session run queue admission did not settle before deadline: "
            + ", ".join(pending_names)
        )

    def _cancel_pending_items(self) -> None:
        """Detach shutdown-pending work inside the owner-controlled async phase."""

        for session_key, queue in self._queues.items():
            keep_count = 1 if session_key in self._running_sessions else 0
            pending = list(queue)[keep_count:]
            while len(queue) > keep_count:
                queue.pop()
            for item in pending:
                self._cancel_before_submit(item)

    async def drain_workers(self, deadline: float) -> None:
        """Drain or cancel every owned per-session worker by one absolute deadline."""

        workers = list(self._workers.values())
        if not workers:
            return
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        _, pending = await asyncio.wait(workers, timeout=remaining)
        if not pending:
            return
        names = sorted(task.get_name() for task in pending)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise TimeoutError(f"session run queue workers exceeded deadline: {names}")

    async def _drain_session(self, session_key: str) -> None:
        queue = self._queues[session_key]
        try:
            while queue:
                item = queue[0]
                if self._sealed and session_key not in self._running_sessions:
                    queue.popleft()
                    self._cancel_before_submit(item)
                    continue
                self._running_sessions.add(session_key)
                if item.queue_owns_admission_event:
                    item.admission_event.set()
                try:
                    result = await item.operation()
                except asyncio.CancelledError:
                    if not item.future.done():
                        item.future.cancel()
                    raise
                except Exception as exc:  # noqa: BLE001
                    if not item.future.done():
                        item.future.set_exception(exc)
                else:
                    if not item.future.done():
                        item.future.set_result(result)
                finally:
                    self._running_sessions.discard(session_key)
                    if queue and queue[0] is item:
                        queue.popleft()
        finally:
            self._running_sessions.discard(session_key)
            self._active_sessions.discard(session_key)
            while queue:
                item = queue.popleft()
                if self._sealed:
                    self._cancel_before_submit(item)
                elif not item.future.done():
                    item.future.cancel()
            self._queues.pop(session_key, None)

    def _cancel_before_submit(self, item: _QueueItem[Any]) -> None:
        error = GatewayShutdownBeforeSubmit()
        item.admission_event.set()
        if not item.future.done():
            item.future.set_exception(error)
        if item.on_cancel is None:
            return
        task = asyncio.get_running_loop().create_task(
            item.on_cancel(error),
            name=(
                "session-run-queue:cancel-lifecycle:"
                f"session_key={item.session_key}:item_id={item.item_id}"
            ),
        )
        self._settlement_tasks.add(task)
        task.add_done_callback(self._settlement_tasks.discard)

    def _worker_done(self, session_key: str, task: asyncio.Task[None]) -> None:
        if self._workers.get(session_key) is task:
            self._workers.pop(session_key, None)
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            asyncio.get_running_loop().call_exception_handler(
                {
                    "message": "session run queue worker failed",
                    "exception": exception,
                    "task": task,
                }
            )
