"""Background queue runner for REPL async message dispatch."""

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Thread
import time
from typing import Callable


@dataclass(frozen=True, slots=True)
class QueuedReplMessage:
    """One queued REPL send task scoped to a concrete session."""

    session_id: str
    text: str


class ReplRunQueue:
    """Serialize REPL sends on a worker thread while input loop stays responsive."""

    def __init__(
        self,
        *,
        process_message: Callable[[QueuedReplMessage], None],
        on_worker_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._process_message = process_message
        self._on_worker_error = on_worker_error
        self._queue: Queue[QueuedReplMessage | None] = Queue()
        self._state_lock = Lock()
        self._active = False
        self._closed = False
        self._worker = Thread(target=self._run, name="nano-cli-repl-run-queue", daemon=True)
        self._worker.start()

    def enqueue(self, *, session_id: str, text: str) -> int:
        """Enqueue one message and return backlog size before enqueue.

        Return value semantics:
        - `0`: no backlog before enqueue (message can start immediately).
        - `>=1`: number of runs/messages ahead of this item.
        """
        with self._state_lock:
            if self._closed:
                raise RuntimeError("repl run queue is closed")
            backlog_before = self._queue.qsize() + (1 if self._active else 0)
            self._queue.put(QueuedReplMessage(session_id=session_id, text=text))
            return backlog_before

    def backlog_size(self) -> int:
        """Return approximate number of active+queued items."""
        with self._state_lock:
            return self._queue.qsize() + (1 if self._active else 0)

    def close(
        self,
        *,
        wait_for_drain: bool,
        drain_timeout_seconds: float | None = None,
        discard_pending: bool = False,
    ) -> bool:
        """Close worker and optionally wait for or discard queued messages.

        Returns:
            True when shutdown finished without leftover backlog, False when timeout hit
            while waiting for active work.
        """
        preserve_head = False
        with self._state_lock:
            if self._closed:
                return True
            preserve_head = wait_for_drain and not self._active and self._queue.qsize() > 0
            self._closed = True
        if discard_pending:
            self._discard_pending_items(preserve_head=preserve_head)
        drained = True
        if wait_for_drain:
            drained = self.wait_for_drain(timeout_seconds=drain_timeout_seconds)
        self._queue.put(None)
        if wait_for_drain or discard_pending:
            self._worker.join(timeout=drain_timeout_seconds)
        return drained

    def discard_pending(self) -> int:
        """Drop queued messages that have not started processing yet and return count."""
        return self._discard_pending_items(preserve_head=False)

    def has_active_work(self) -> bool:
        """Return whether a worker is currently processing one message."""
        with self._state_lock:
            return self._active

    def _discard_pending_items(self, *, preserve_head: bool) -> int:
        discarded = 0
        buffered: list[QueuedReplMessage | None] = []
        preserved_head = not preserve_head
        while True:
            try:
                item = self._queue.get_nowait()
            except Empty:
                break
            if item is None:
                buffered.append(item)
                self._queue.task_done()
                continue
            if not preserved_head:
                buffered.append(item)
                preserved_head = True
            else:
                discarded += 1
            self._queue.task_done()
        for item in buffered:
            self._queue.put(item)
        return discarded

    def wait_for_drain(self, *, timeout_seconds: float | None = None) -> bool:
        """Wait until active/queued work is drained.

        Returns:
            True when queue drained, False when timeout reached.
        """
        deadline = None if timeout_seconds is None else (time.monotonic() + max(timeout_seconds, 0.0))
        while True:
            if self.backlog_size() == 0:
                return True
            if deadline is not None and time.monotonic() >= deadline:
                # One final check avoids false timeout when drain races deadline.
                return self.backlog_size() == 0
            time.sleep(0.05)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            with self._state_lock:
                self._active = True
            try:
                self._process_message(item)
            except Exception as exc:  # pragma: no cover - defensive worker boundary
                if self._on_worker_error is not None:
                    self._on_worker_error(exc)
            finally:
                with self._state_lock:
                    self._active = False
                self._queue.task_done()
