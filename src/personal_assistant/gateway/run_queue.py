"""Per-session FIFO execution queues for gateway inbound runs."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class SessionRunQueue:
    """Serialize work per session while allowing cross-session concurrency.

    Notes:
        Each session key owns its own deque and active worker flag. This keeps one
        canonical structure: FIFO within a session, natural parallelism across
        different session keys because their workers run in separate asyncio tasks.
    """

    def __init__(self) -> None:
        self._queues: dict[str, deque[tuple[asyncio.Future[T], Callable[[], Awaitable[T]]]]] = {}
        self._active_sessions: set[str] = set()

    async def submit(self, session_key: str, operation: Callable[[], Awaitable[T]]) -> T:
        """Queue one coroutine factory under the given session key.

        Args:
            session_key: Gateway-local session key controlling serialization scope.
            operation: Zero-arg coroutine factory executed when the item reaches the
                head of the session FIFO.

        Returns:
            The awaited result returned by ``operation``.
        """

        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        queue = self._queues.setdefault(session_key, deque())
        queue.append((future, operation))
        if session_key not in self._active_sessions:
            self._active_sessions.add(session_key)
            loop.create_task(self._drain_session(session_key))
        return await future

    async def _drain_session(self, session_key: str) -> None:
        queue = self._queues[session_key]
        try:
            while queue:
                future, operation = queue[0]
                try:
                    result = await operation()
                except Exception as exc:  # noqa: BLE001
                    if not future.done():
                        future.set_exception(exc)
                else:
                    if not future.done():
                        future.set_result(result)
                finally:
                    queue.popleft()
        finally:
            self._active_sessions.discard(session_key)
            if not queue:
                self._queues.pop(session_key, None)
