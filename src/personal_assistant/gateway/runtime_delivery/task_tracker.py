"""Own detached runtime-delivery tasks through Gateway shutdown."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import logging
from typing import Any

from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore

_log = logging.getLogger("personal_assistant.gateway.runtime_delivery.task_tracker")


class RuntimeDeliveryTaskTracker:
    """Create and drain every delivery awaitable that leaves its caller's stack."""

    def __init__(self, *, context_store: RunDeliveryContextStore | None = None) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._tasks_by_run: dict[str, set[asyncio.Task[None]]] = {}
        self._preserved_tasks: set[asyncio.Task[None]] = set()
        self._context_store = context_store
        self._admitted: dict[str, int] = {}
        self._admitted_empty: dict[str, asyncio.Event] = {}
        self._closed = False

    def start(
        self,
        awaitable: Awaitable[object],
        *,
        name: str,
        run_id: str | None = None,
        preserve_on_reset: bool = False,
    ) -> None:
        """Accept one detached delivery awaitable under a semantic task name.

        Args:
            awaitable: Delivery operation to run on the current event loop.
            name: Stable event/run label used in shutdown diagnostics.
            run_id: Run whose context must survive this delivery operation.
            preserve_on_reset: Keep resource finalizers alive when public output is revoked.

        Raises:
            RuntimeError: If delivery admission has already closed.
        """

        if self._closed:
            self._dispose_rejected(awaitable)
            raise RuntimeError("runtime delivery task tracker is closed")

        retained = bool(
            run_id is not None
            and self._context_store is not None
            and self._context_store.retain(run_id)
        )
        started = False

        async def _run() -> None:
            nonlocal started
            started = True
            try:
                await awaitable
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                # Delivery failures have always been isolated from Kernel event
                # production. The tracker preserves that boundary while making the
                # detached operation visible to shutdown.
                _log.exception("runtime delivery task failed: %s", name)

        task = asyncio.get_running_loop().create_task(
            _run(),
            name=f"runtime-delivery:{name}",
        )
        self._tasks.add(task)
        if preserve_on_reset:
            self._preserved_tasks.add(task)
        if run_id is not None:
            self._tasks_by_run.setdefault(run_id, set()).add(task)

        def _discard(done: asyncio.Task[None]) -> None:
            self._tasks.discard(done)
            self._preserved_tasks.discard(done)
            if not started:
                self._dispose_rejected(awaitable)
            if retained and self._context_store is not None and run_id is not None:
                self._context_store.release(run_id)
            if run_id is not None:
                tasks = self._tasks_by_run.get(run_id)
                if tasks is not None:
                    tasks.discard(done)
                    if not tasks:
                        self._tasks_by_run.pop(run_id, None)

        task.add_done_callback(_discard)

    def cancel_run(self, run_id: str) -> None:
        """Cancel delivery work that has not crossed the reset visibility boundary."""

        for task in tuple(self._tasks_by_run.get(run_id, ())):
            if task not in self._preserved_tasks:
                task.cancel()

    def admit_publication(self, run_id: str) -> bool:
        """Register a visible request on the Gateway loop, after async qualification."""
        if self._context_store is None or not self._context_store.can_publish(run_id):
            return False
        self._admitted[run_id] = self._admitted.get(run_id, 0) + 1
        self._admitted_empty.setdefault(run_id, asyncio.Event()).clear()
        return True

    def release_publication(self, run_id: str) -> None:
        """Release one admitted public request from its I/O finally block."""
        remaining = self._admitted[run_id] - 1
        if remaining:
            self._admitted[run_id] = remaining
        else:
            self._admitted.pop(run_id)
            self._admitted_empty.pop(run_id).set()

    async def drain_admitted(self, run_ids: tuple[str, ...]) -> None:
        """Wait only for already-admitted I/O, never preparation or gate waiters."""
        events = [
            self._admitted_empty[run_id]
            for run_id in run_ids
            if run_id in self._admitted_empty
        ]
        if events:
            await asyncio.gather(*(event.wait() for event in events))

    async def drain_run(self, run_id: str) -> None:
        """Wait for already-permitted output from one run to finish sending."""

        while tasks := tuple(self._tasks_by_run.get(run_id, ())):
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close_and_drain(self, deadline: float) -> None:
        """Seal admission and drain accepted tasks by one absolute deadline.

        Args:
            deadline: Absolute ``loop.time()`` deadline shared by Gateway shutdown.

        Raises:
            TimeoutError: If tasks remain at the deadline. Remaining tasks are
                cancelled and awaited before the error is raised.
        """

        self._closed = True
        loop = asyncio.get_running_loop()
        while self._tasks:
            snapshot = set(self._tasks)
            remaining = deadline - loop.time()
            if remaining <= 0:
                await self._cancel_leftovers(snapshot)
                raise TimeoutError(self._timeout_message(snapshot))
            done, pending = await asyncio.wait(snapshot, timeout=remaining)
            self._tasks.difference_update(done)
            if pending:
                await self._cancel_leftovers(pending)
                raise TimeoutError(self._timeout_message(pending))

    @staticmethod
    def _dispose_rejected(awaitable: Awaitable[object]) -> None:
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
            return
        if isinstance(awaitable, asyncio.Future):
            awaitable.cancel()

    async def _cancel_leftovers(self, tasks: set[asyncio.Task[None]]) -> None:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.difference_update(tasks)

    @staticmethod
    def _timeout_message(tasks: set[asyncio.Task[Any]]) -> str:
        names = ", ".join(sorted(task.get_name() for task in tasks))
        return f"runtime delivery drain timed out: {names}"
