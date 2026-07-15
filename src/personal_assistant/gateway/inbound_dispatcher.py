"""Bridge synchronous channel callbacks onto the Gateway event loop."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future as ConcurrentFuture
import logging
import threading
from typing import Any

from personal_assistant.channels.base import InboundMessage

_log = logging.getLogger(__name__)


class InboundDispatcher:
    """Own every accepted ``handle_inbound`` root across loop/thread boundaries."""

    def __init__(self, pipeline: Any) -> None:
        self._pipeline = pipeline
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sealed = False
        self._lock = threading.Lock()
        self._root_sequence = 0
        self._loop_roots: set[asyncio.Task[None]] = set()
        self._thread_roots: dict[ConcurrentFuture[None], str] = {}
        self._thread_loop_roots: dict[str, asyncio.Task[None]] = {}

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the single Gateway loop used for all inbound coroutine roots."""

        self._loop = loop

    def __call__(self, message: InboundMessage) -> None:
        """Accept and track one callback, or reject it after synchronous seal.

        Args:
            message: Normalized channel inbound message.

        Raises:
            RuntimeError: When called before the Gateway event loop is bound.
        """

        loop = self._loop
        if loop is None:
            raise RuntimeError("gateway runtime loop is not ready")
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        with self._lock:
            if self._sealed:
                return
            self._root_sequence += 1
            root_name = f"inbound-root:{self._root_sequence}"
            coroutine = self._run_root(
                message,
                root_name=root_name,
                thread_boundary=running_loop is not loop,
            )
            if running_loop is loop:
                task = loop.create_task(coroutine, name=root_name)
                self._loop_roots.add(task)
                task.add_done_callback(self._loop_root_done)
                return
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
            self._thread_roots[future] = root_name
            future.add_done_callback(self._thread_root_done)

    def seal(self) -> None:
        """Synchronously reject future callbacks and seal pipeline admission."""

        with self._lock:
            if self._sealed:
                return
            self._sealed = True
        self._pipeline.seal()

    async def settle_admission(self, deadline: float) -> None:
        """Wait for accepted pipeline work to cross submit-or-rollback."""

        await self._pipeline.settle_admission(deadline)

    async def drain(self, deadline: float) -> None:
        """Drain all accepted root tasks/futures by one absolute deadline.

        Args:
            deadline: Absolute monotonic deadline from the bound Gateway loop.

        Raises:
            TimeoutError: When roots require cancellation at the shared deadline.
        """

        with self._lock:
            loop_roots = list(self._loop_roots)
            thread_roots = dict(self._thread_roots)
            thread_loop_roots = dict(self._thread_loop_roots)
        started_thread_names = set(thread_loop_roots)
        wrapped = [
            asyncio.wrap_future(future)
            for future, root_name in thread_roots.items()
            if root_name not in started_thread_names
        ]
        roots: list[asyncio.Future[Any] | asyncio.Task[Any]] = [
            *loop_roots,
            *thread_loop_roots.values(),
            *wrapped,
        ]
        if not roots:
            return
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        _, pending = await asyncio.wait(roots, timeout=remaining)
        if not pending:
            return
        for root in pending:
            root.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise TimeoutError(f"inbound roots exceeded deadline: {len(pending)}")

    async def _run_root(
        self,
        message: InboundMessage,
        *,
        root_name: str,
        thread_boundary: bool = False,
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            task.set_name(root_name)
            if thread_boundary:
                with self._lock:
                    self._thread_loop_roots[root_name] = task
                task.add_done_callback(
                    lambda done, name=root_name: self._thread_loop_root_done(
                        name, done
                    )
                )
        await self._pipeline.handle_inbound(message)

    def _loop_root_done(self, task: asyncio.Task[None]) -> None:
        with self._lock:
            self._loop_roots.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            _log.error("inbound root failed", exc_info=error)

    def _thread_root_done(self, future: ConcurrentFuture[None]) -> None:
        with self._lock:
            self._thread_roots.pop(future, None)
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            _log.error("threadsafe inbound root failed", exc_info=error)

    def _thread_loop_root_done(
        self, root_name: str, task: asyncio.Task[None]
    ) -> None:
        with self._lock:
            if self._thread_loop_roots.get(root_name) is task:
                self._thread_loop_roots.pop(root_name, None)
